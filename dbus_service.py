'''DbusService and PvInverterRegistry'''

# File specific rules
# pylint: disable=broad-except, import-error, wrong-import-order, wrong-import-position

# region [Imports]

# system imports:
import configparser
import os
import platform
import sys
import logging
import time
from json import dumps as json_dumps
import requests  # for http GET
from requests.auth import HTTPDigestAuth

# our imports:
import constants
from helpers import *

# victron imports:
import dbus

sys.path.insert(
    1,
    os.path.join(
        os.path.dirname(__file__),
        "/opt/victronenergy/dbus-systemcalc-py/ext/velib_python",
    ),
)
from vedbus import VeDbusService  # noqa - must be placed after the sys.path.insert

# endregion


class DbusServiceRegistry(type):
    """
    Metaclass for registering and iterating over D-Bus services.

    This metaclass maintains a registry of D-Bus services and provides an iterator
    to iterate over the registered services.

    Methods:
        __iter__(cls): Returns an iterator over the registered D-Bus services.
    """
    def __iter__(cls):
        return iter(cls._registry)


class DbusService:
    '''Main class to register PV Inverter in DBUS'''
    __metaclass__ = DbusServiceRegistry
    _registry = []
    _meter_data = None
    _test_meter_data = None
    _servicename = None

    def __init__(
        self,
        servicename,
        actual_inverter,
        istemplate=False,
    ):

        if servicename == "testing":
            self.max_age_ts = 600
            self.pvinverternumber = actual_inverter
            self.useyieldday = False
            return

        self._registry.append(self)
        self._last_update = 0
        self._servicename = servicename
        self.last_update_successful = False

        # Initiale own properties
        self.esptype = None
        self.meter_data = None
        self.dtuvariant = None

        # Initialize error handling properties
        self.error_mode = None
        self.retry_after_seconds = 0
        self.min_retries_until_fail = 0
        self.error_state_after_seconds = 0
        self.failed_update_count = 0
        self.reset_statuscode_on_next_success = False

        if not istemplate:
            self._read_config_dtu(actual_inverter)
            self.numberofinverters = self.get_number_of_inverters()
        else:
            self._read_config_template(actual_inverter)

        logging.info("%s /DeviceInstance = %d", servicename, self.deviceinstance)

        # Allow for multiple Instance per process in DBUS
        dbus_conn = (
            dbus.SessionBus()
            if "DBUS_SESSION_BUS_ADDRESS" in os.environ
            else dbus.SystemBus(private=True)
        )

        self._dbusservice = VeDbusService(f"{servicename}.http_{self.deviceinstance}", bus=dbus_conn, register=False)
        self._paths = (constants.PVINVERTER_PATHS
                       if servicename == "com.victronenergy.pvinverter"
                       else constants.VICTRON_PATHS)

        # Create the management objects, as specified in the ccgx dbus-api document
        self._dbusservice.add_path("/Mgmt/ProcessName", __file__)
        self._dbusservice.add_path("/Mgmt/ProcessVersion",
                                   "Unkown version, and running on Python " + platform.python_version())
        self._dbusservice.add_path("/Mgmt/Connection", constants.PRODUCTNAME + " - " + constants.CONNECTION)

        # Fetch serial + OpenDTU devinfo once so management paths can be populated
        # with real hardware/firmware metadata instead of placeholders.
        self.serial = self._get_serial(self.pvinverternumber)
        self.devinfo = self._fetch_devinfo_safe()
        # Seed /Ac/MaxPower and /Ac/PowerLimit from OpenDTU before add_path; writing
        # them later would emit PropertiesChanged and round-trip back as an external
        # Set that our onchangecallback re-applies to OpenDTU, stomping on user limits.
        limit_entry = self._fetch_limit_entry_safe()
        initial_max_power, initial_power_limit = self._initial_power_limit_from_entry(limit_entry)
        # If the initial fetch failed, _refresh_limit_status will seed these paths
        # on its first successful call. Track the state so the seed fires at most once.
        self._limit_seeded = limit_entry is not None

        product_name = (self.devinfo.get("hw_model_name") if self.devinfo else None) or self._get_name()
        firmware_version = self._format_firmware_version() or read_version('version.txt')
        hardware_version = self._decode_version(
            self.devinfo.get("hw_version") if self.devinfo else None) or 0
        initial_status = (constants.STATUSCODE_ERROR
                          if self.devinfo is not None and not is_true(self.devinfo.get("valid_data", True))
                          else constants.STATUSCODE_STARTUP)

        self.polling_interval = self._get_polling_interval()

        # Create the mandatory objects
        self._dbusservice.add_path("/DeviceInstance", self.deviceinstance)
        self._dbusservice.add_path("/ProductId", 0xFFFF)  # id assigned by Victron Support from SDM630v2.py
        self._dbusservice.add_path("/ProductName", product_name)
        self._dbusservice.add_path("/CustomName", self._get_name())
        logging.info(f"Name of Inverters found: {self._get_name()}")
        connected = int(is_true(self.devinfo.get("valid_data"))) if self.devinfo else 1
        self._dbusservice.add_path("/Connected", connected)

        self._dbusservice.add_path("/Latency", self.polling_interval)
        self._dbusservice.add_path("/FirmwareVersion", firmware_version)
        self._dbusservice.add_path("/HardwareVersion", hardware_version)
        self._dbusservice.add_path("/Serial", self.serial)
        self._dbusservice.add_path("/UpdateIndex", 0)
        # StatusCode starts at Startup(0); first successful update_dbus_values() transitions to Running/Standby.
        # devinfo.valid_data=false at startup already flags ERROR.
        self._dbusservice.add_path("/StatusCode", initial_status)
        if servicename == "com.victronenergy.pvinverter":
            self._dbusservice.add_path("/Position", self.acposition)
            self._dbusservice.add_path("/PositionIsAdjustable", 1)

        # If the Servicname is an (AC-)Inverter, add the Mode path (to show it as ON)
        # Also, we will set different paths and variables in the _update(self) method.
        # for this device class. For more information about the paths and ServiceNames...
        # @see: https://github.com/victronenergy/venus/wiki/dbus
        if self._servicename == "com.victronenergy.inverter":
            # Set Mode to 2 to show it as ON
            # 2=On;4=Off;5=Eco
            self._dbusservice.add_path("/Mode", 2)
            # set the SystemState flaf to 9=Inverting
            # /SystemState/State     ->   0: Off
            #                        ->   1: Low power
            #                        ->   9: Inverting
            self._dbusservice.add_path("/State", 9)

        # add path values to dbus
        initial_overrides = {
            "/Ac/MaxPower": initial_max_power,
            "/Ac/PowerLimit": initial_power_limit,
        }
        for path, settings in self._paths.items():
            initial_value = initial_overrides.get(path, settings["initial"])
            self._dbusservice.add_path(
                path,
                initial_value,
                gettextcallback=settings["textformat"],
                writeable=True,
                onchangecallback=self._handlechangedvalue,
            )

        self._dbusservice.register()

        self.last_polling = 0

    @staticmethod
    def get_ac_inverter_state(current):
        '''return the state of the inverter based on the current value'''
        try:
            float_current = float(current)
        except ValueError:
            float_current = 0
        if float_current > 0:
            ac_inverter_state = 9  # = Inverting
        else:
            ac_inverter_state = 0  # = Off
        return ac_inverter_state

    def _handlechangedvalue(self, path, value):
        logging.debug("someone else updated %s to %s", path, value)
        if path == "/Ac/PowerLimit" and self.dtuvariant == constants.DTUVARIANT_OPENDTU:
            return self._apply_power_limit(value)
        return True  # accept the change

    @staticmethod
    def _get_config():
        config = configparser.ConfigParser()
        config.read(f"{(os.path.dirname(os.path.realpath(__file__)))}/config.ini")
        return config

    @staticmethod
    def get_processed_meter_value(meter_data: dict, path_to_value, default_value: any, factor: int = 1) -> any:
        '''return the processed meter value by applying the factor and return a default value due an Exception'''
        raw_value = get_value_by_path(meter_data, path_to_value)
        raw_value = convert_to_expected_type(raw_value, float, default_value)
        if isinstance(raw_value, (float, int)):
            value = float(raw_value * float(factor))
        else:
            value = default_value

        return value

    # read config file
    def _read_config_dtu(self, actual_inverter):
        config = self._get_config()
        self.pvinverternumber = actual_inverter
        self.dtuvariant = str(config["DEFAULT"]["DTU"])
        if self.dtuvariant not in (constants.DTUVARIANT_OPENDTU, constants.DTUVARIANT_AHOY):
            raise ValueError(f"Error in config.ini: DTU must be one of \
                {constants.DTUVARIANT_OPENDTU}, \
                {constants.DTUVARIANT_AHOY}")
        self.deviceinstance = int(config[f"INVERTER{self.pvinverternumber}"]["DeviceInstance"])
        self.acposition = int(get_config_value(config, "AcPosition", "INVERTER", self.pvinverternumber))
        self.useyieldday = int(get_config_value(config, "useYieldDay", "DEFAULT", "", 0))
        self.pvinverterphase = str(config[f"INVERTER{self.pvinverternumber}"]["Phase"])
        self.host = get_config_value(config, "Host", "INVERTER", self.pvinverternumber)
        self.username = get_config_value(config, "Username", "DEFAULT", "", self.pvinverternumber)
        self.password = get_config_value(config, "Password", "DEFAULT", "", self.pvinverternumber)
        self.digestauth = is_true(get_config_value(config, "DigestAuth", "INVERTER", self.pvinverternumber, False))

        try:
            self.max_age_ts = int(config["DEFAULT"]["MaxAgeTsLastSuccess"])
        except (KeyError, ValueError) as ex:
            logging.warning("MaxAgeTsLastSuccess: %s", ex)
            logging.warning("MaxAgeTsLastSuccess not set, using default")
            self.max_age_ts = 600

        self.dry_run = is_true(get_default_config(config, "DryRun", False))
        self.pollinginterval = int(get_config_value(config, "ESP8266PollingIntervall", "DEFAULT", "", 10000))
        # The mainloop is single threaded and fetches every inverter separately and
        # synchronously, so poll rate and retry count decide how long dbus method calls on this
        # service stay unanswered: worst case = inverters x tries x HTTPTimeout. With five
        # inverters, three tries and a 1.5s timeout that is 27.5s - long enough for GetValue
        # callers to run into org.freedesktop.DBus.Error.NoReply while the DTU is slow.
        self.opendtu_polling_interval = int(get_config_value(config, "OpenDTUPollingIntervall", "DEFAULT", "", 5000))
        self.max_fetch_tries = int(get_config_value(config, "MaxFetchTries", "DEFAULT", "", 3))
        self.meter_data = 0
        self.httptimeout = get_default_config(config, "HTTPTimeout", 2.5)
        self._load_error_handling_config(config)

    def _read_config_template(self, template_number):
        config = self._get_config()
        self.pvinverternumber = template_number
        self.custpower = config[f"TEMPLATE{template_number}"]["CUST_Power"].split("/")
        self.custpower_factor = config[f"TEMPLATE{template_number}"]["CUST_Power_Mult"]
        self.custpower_default = get_config_value(config,  "CUST_Power_Default", "TEMPLATE", template_number, None)
        self.custtotal = config[f"TEMPLATE{template_number}"]["CUST_Total"].split("/")
        self.custtotal_factor = config[f"TEMPLATE{template_number}"]["CUST_Total_Mult"]
        self.custtotal_default = get_config_value(config,  "CUST_Total_Default", "TEMPLATE", template_number, None)
        self.custvoltage = config[f"TEMPLATE{template_number}"]["CUST_Voltage"].split("/")
        self.custvoltage_default = get_config_value(config,  "CUST_Voltage_Default", "TEMPLATE", template_number, None)
        self.custapipath = config[f"TEMPLATE{template_number}"]["CUST_API_PATH"]
        self.serial = str(config[f"TEMPLATE{template_number}"]["CUST_SN"])
        self.pollinginterval = int(config[f"TEMPLATE{template_number}"]["CUST_POLLING"])
        self.host = config[f"TEMPLATE{template_number}"]["Host"]
        self.username = config[f"TEMPLATE{template_number}"]["Username"]
        self.password = config[f"TEMPLATE{template_number}"]["Password"]
        self.dtuvariant = constants.DTUVARIANT_TEMPLATE
        self.deviceinstance = int(config[f"TEMPLATE{template_number}"]["DeviceInstance"])
        self.customname = config[f"TEMPLATE{template_number}"]["Name"]
        self.acposition = int(config[f"TEMPLATE{template_number}"]["AcPosition"])
        self.useyieldday = int(get_config_value(config, "useYieldDay", "DEFAULT", "", 0))
        self.pvinverterphase = str(config[f"TEMPLATE{template_number}"]["Phase"])
        self.digestauth = is_true(get_config_value(config, "DigestAuth", "TEMPLATE", template_number, False))

        try:
            self.custcurrent = config[f"TEMPLATE{template_number}"]["CUST_Current"].split("/")
        except Exception:
            # set to undefined because get_nested will solve this to 0
            self.custcurrent = "[undefined]"
            logging.debug("CUST_Current not set")
        self.custcurrent_default = get_config_value(config,  "CUST_Current_Default", "TEMPLATE", template_number, None)

        try:
            self.custdcvoltage = config[f"TEMPLATE{template_number}"]["CUST_DCVoltage"].split("/")
        except Exception:
            # set to undefined because get_nested will solve this to 0
            self.custdcvoltage = "[undefined]"
            logging.debug("CUST_DCVoltage not set")
        self.custdcvoltage_default = get_config_value(
            config,  "CUST_DCVoltage_Default", "TEMPLATE", template_number, None)

        try:
            self.max_age_ts = int(config["DEFAULT"]["MaxAgeTsLastSuccess"])
        except (KeyError, ValueError) as ex:
            logging.warning("MaxAgeTsLastSuccess: %s", ex)
            logging.warning("MaxAgeTsLastSuccess not set, using default")
            self.max_age_ts = 600

        self.dry_run = is_true(get_default_config(config, "DryRun", False))
        self.meter_data = 0
        self.httptimeout = get_default_config(config, "HTTPTimeout", 2.5)
        self._load_error_handling_config(config)

    def _load_error_handling_config(self, config):
        '''Loads error handling configuration values from the provided config object.'''

        self.error_mode = get_default_config(config, "ErrorMode", constants.MODE_RETRYCOUNT).strip()
        self.retry_after_seconds = int(get_default_config(config, "RetryAfterSeconds", 180))
        self.min_retries_until_fail = int(get_default_config(config, "MinRetriesUntilFail", 3))
        self.error_state_after_seconds = int(get_default_config(config, "ErrorStateAfterSeconds", 0))

    # get the Serialnumber
    def _get_serial(self, pvinverternumber):

        meter_data = None
        serial = None
        if self.dtuvariant in (constants.DTUVARIANT_AHOY, constants.DTUVARIANT_OPENDTU):
            meter_data = self._get_data()

            if self.dtuvariant == constants.DTUVARIANT_AHOY:
                if not meter_data["inverter"][pvinverternumber]["name"]:
                    raise ValueError("Response does not contain name")
                serial = meter_data["inverter"][pvinverternumber]["serial"]

            elif self.dtuvariant == constants.DTUVARIANT_OPENDTU:
                if not meter_data["inverters"][pvinverternumber]["serial"]:
                    raise ValueError("Response does not contain serial attribute try name")
                serial = meter_data["inverters"][pvinverternumber]["serial"]

        elif self.dtuvariant == constants.DTUVARIANT_TEMPLATE:
            serial = self.serial

        return serial

    def _get_name(self):
        if self.dtuvariant in (constants.DTUVARIANT_OPENDTU, constants.DTUVARIANT_AHOY):
            meter_data = self._get_data()
        meter_data = None
        if self.dtuvariant in (constants.DTUVARIANT_OPENDTU, constants.DTUVARIANT_AHOY):
            meter_data = self._get_data()
        if self.dtuvariant == constants.DTUVARIANT_AHOY:
            name = meter_data["inverter"][self.pvinverternumber]["name"]
        elif self.dtuvariant == constants.DTUVARIANT_OPENDTU:
            name = meter_data["inverters"][self.pvinverternumber]["name"]
        else:
            name = self.customname
        return name

    def get_number_of_inverters(self):
        '''return number of inverters in JSON response'''
        meter_data = self._get_data()
        if self.dtuvariant == constants.DTUVARIANT_AHOY:
            numberofinverters = len(meter_data["inverter"])
        else:  # Assuming the only other option is constants.DTUVARIANT_OPENDTU
            numberofinverters = len(meter_data["inverters"])
        logging.info("Number of Inverters found: %s", numberofinverters)
        return numberofinverters

    def _get_dtu_variant(self):
        return self.dtuvariant

    def _get_polling_interval(self):
        meter_data = self._get_data()
        if self.dtuvariant == constants.DTUVARIANT_AHOY:
            # Check for ESP8266 and limit polling
            try:
                self.esptype = meter_data["generic"]["esp_type"]
            except Exception:  # pylint: disable=broad-except
                self.esptype = meter_data["system"]["esp_type"]

            if self.esptype == "ESP8266":
                polling_interval = self.pollinginterval
                logging.info(f"ESP8266 detected, polling interval {polling_interval/1000} Sek.")
            else:
                polling_interval = 5000

        elif self.dtuvariant == constants.DTUVARIANT_OPENDTU:
            polling_interval = self.opendtu_polling_interval

        elif self.dtuvariant == constants.DTUVARIANT_TEMPLATE:
            polling_interval = self.pollinginterval
        return polling_interval

    def _get_status_url(self):
        url = None
        if self.dtuvariant == constants.DTUVARIANT_OPENDTU:
            url = self.get_opendtu_base_url() + "/livedata/status"
        elif self.dtuvariant == constants.DTUVARIANT_AHOY:
            url = self.get_ahoy_base_url() + "/live"
        elif self.dtuvariant == constants.DTUVARIANT_TEMPLATE:
            url = self.get_template_base_url()
        else:
            logging.error('no dtuvariant set')
        return url

    def get_opendtu_base_url(self):
        '''Get API base URL for all OpenDTU calls'''
        return f"http://{self.host}/api"

    def get_ahoy_base_url(self):
        '''Get API base URL for all Ahoy calls'''
        return f"http://{self.host}/api"

    def get_template_base_url(self):
        '''Get API base URL for all Template calls'''
        return f"http://{self.host}/{self.custapipath}"

    def _refresh_data(self):
        '''Fetch new data from the DTU API and store in locally if successful.'''

        if self.pvinverternumber != 0 and self.dtuvariant != constants.DTUVARIANT_TEMPLATE:
            # only fetch new data when called for inverter 0
            # (background: data is kept at class level for all inverters)
            return

        url = self._get_status_url()
        meter_data = self.fetch_url(url)

        if self.dtuvariant == constants.DTUVARIANT_OPENDTU:
            self.check_opendtu_data(meter_data)

        if self.dtuvariant == constants.DTUVARIANT_AHOY:
            self.check_and_enrich_ahoy_data(meter_data)

        self.store_for_later_use(meter_data)

    def store_for_later_use(self, meter_data):
        '''Store meter data for later use in other methods'''
        if self.dtuvariant == constants.DTUVARIANT_TEMPLATE:
            self.meter_data = meter_data
        else:
            DbusService._meter_data = meter_data

    def check_and_enrich_ahoy_data(self, meter_data):
        ''' Check if Ahoy data is valid and enrich it with additional data'''
        if not "iv" in meter_data:
            raise ValueError("You do not have the latest Ahoy Version to run this script,"
                             "please upgrade your Ahoy to at least version 0.5.93")
         # Check for Attribute (inverter)
        if (self._servicename == "com.victronenergy.inverter" and
                not "fld_names" in meter_data):
            raise ValueError("Response from ahoy does not contain fld_names in data")
        # Check for an additonal Attribute
        if not "ch0_fld_names" in meter_data:
            raise ValueError("Response from ahoy does not contain ch0_fld_names data")
        # not needed: meter_data["record"] = self.fetch_ahoy_record_data()

        # add the field "inverter" to meter_data:
        # This will contain an array of the "iv" data from all inverters.
        meter_data["inverter"] = []
        for inverter_number in range(len(meter_data["iv"])):
            if is_true(meter_data["iv"][inverter_number]):
                iv_data = self.fetch_ahoy_iv_data(inverter_number)
                while len(meter_data["inverter"]) < inverter_number:
                    # there was a gap in the sequence of inverter numbers -> fill in a dummy value
                    meter_data["inverter"].append({})
                meter_data["inverter"].append(iv_data)

    def check_opendtu_data(self, meter_data):
        ''' Check if OpenDTU data has the right format'''
        # Check for OpenDTU Version
        if not "serial" in meter_data["inverters"][self.pvinverternumber]:
            raise ValueError("You do not have the latest OpenDTU Version to run this script,"
                             "please upgrade your OpenDTU to at least version 4.4.3")

    def fetch_opendtu_iv_data(self, inverter_serial):
        '''Fetch inverter data from OpenDTU device for one inverter'''
        iv_url = self._get_status_url() + "?inv=" + inverter_serial
        logging.debug(f"Inverter URL: {iv_url}")
        return self.fetch_url(iv_url)

    def fetch_opendtu_devinfo(self, inverter_serial):
        '''Fetch device info (firmware/hardware metadata) from OpenDTU for one inverter.'''
        url = f"{self.get_opendtu_base_url()}/devinfo/status?inv={inverter_serial}"
        logging.debug(f"Devinfo URL: {url}")
        return self.fetch_url(url)

    def _fetch_devinfo_safe(self):
        '''OpenDTU only: one-shot devinfo fetch at startup. Returns dict or None on failure.'''
        if self.dtuvariant != constants.DTUVARIANT_OPENDTU:
            return None
        try:
            return self.fetch_opendtu_devinfo(self.serial)
        except Exception as error:
            logging.warning(f"devinfo fetch failed: {error}")
            return None

    def _fetch_limit_entry_safe(self):
        '''OpenDTU only: one-shot /api/limit/status fetch for this inverter at startup.
           Returns the per-serial entry dict or None on failure.'''
        if self.dtuvariant != constants.DTUVARIANT_OPENDTU:
            return None
        try:
            status = self.fetch_url(f"{self.get_opendtu_base_url()}/limit/status")
            return status.get(self.serial)
        except Exception as error:
            logging.warning(f"limit status fetch failed: {error}")
            return None

    @staticmethod
    def _initial_power_limit_from_entry(entry):
        '''Derive (max_power, power_limit) pair from a /api/limit/status entry.
           Either value may be None if the entry is missing or incomplete.'''
        if not entry:
            return (None, None)
        max_power = entry.get("max_power")
        limit_relative = entry.get("limit_relative")
        power_limit = None
        if max_power is not None and limit_relative is not None:
            power_limit = max_power * float(limit_relative) / 100.0
        return (max_power, power_limit)

    @staticmethod
    def _decode_version(value):
        '''Decode OpenDTU version fields. Strings pass through; ints are split into
           2-digit groups from the right (e.g. 10027 -> "1.0.27", 101 -> "0.1.1").'''
        if value is None:
            return None
        if isinstance(value, str):
            return value
        if isinstance(value, int):
            return f"{value // 10000}.{(value // 100) % 100}.{value % 100}"
        return str(value)

    def _format_firmware_version(self):
        '''Combine devinfo fw_build_version and fw_build_datetime into a display string.'''
        if not self.devinfo:
            return None
        fw_ver = self._decode_version(self.devinfo.get("fw_build_version"))
        fw_dt = self.devinfo.get("fw_build_datetime")
        if fw_ver and fw_dt:
            return f"{fw_ver} ({fw_dt})"
        return fw_ver or fw_dt

    def _refresh_limit_status(self):
        '''OpenDTU only: fetch /api/limit/status and mirror limit_set_status to
           /StatusCode. Returns the limit_set_status string (or None) so callers can
           poll through a "Pending" phase. /Ac/MaxPower and /Ac/PowerLimit are seeded
           at init via add_path; if that initial fetch failed, this function performs
           a one-shot fallback seed (guarded by echo suppression in _handlechangedvalue
           so the internal write doesn't round-trip back as a POST).'''
        if self.dtuvariant != constants.DTUVARIANT_OPENDTU:
            return None
        url = f"{self.get_opendtu_base_url()}/limit/status"
        status = self.fetch_url(url)
        entry = status.get(self.serial)
        if not entry:
            logging.warning(f"No limit status entry for serial {self.serial}")
            return None
        if not getattr(self, "_limit_seeded", True):
            # Mark seeded before writes so any re-entrant _refresh_limit_status (via
            # onchangecallback -> _apply_power_limit -> _wait_for_limit_settled) skips.
            self._limit_seeded = True
            max_power, power_limit = self._initial_power_limit_from_entry(entry)
            if max_power is not None:
                self._dbusservice["/Ac/MaxPower"] = max_power
            if power_limit is not None:
                self._dbusservice["/Ac/PowerLimit"] = power_limit
        limit_set_status = entry.get("limit_set_status")
        if limit_set_status == "Ok":
            self._dbusservice["/StatusCode"] = constants.STATUSCODE_RUNNING
        elif limit_set_status == "Pending":
            # Transient: inverter hasn't acknowledged the new limit yet. Leave
            # /StatusCode unchanged so callers can poll without flapping.
            logging.debug(f"limit_set_status=Pending for serial {self.serial}")
        else:
            logging.warning(f"limit_set_status={limit_set_status} for serial {self.serial}")
            self._dbusservice["/StatusCode"] = constants.STATUSCODE_ERROR
        return limit_set_status

    def _wait_for_limit_settled(self, timeout=5.0, interval=0.5):
        '''Poll _refresh_limit_status until limit_set_status leaves "Pending" or
           timeout elapses. Returns the final status string (or None).'''
        deadline = time.time() + timeout
        status = None
        while True:
            try:
                status = self._refresh_limit_status()
            except Exception as error:
                logging.warning(f"Limit status refresh failed during poll: {error}")
                return status
            if status != "Pending":
                return status
            if time.time() >= deadline:
                logging.warning(
                    f"limit_set_status still Pending after {timeout:.1f}s for serial {self.serial}")
                return status
            time.sleep(interval)

    def _apply_power_limit(self, watts):
        '''Write /Ac/PowerLimit -> POST /api/limit/config (absolute watts, non-persistent).
           Return True to accept the DBus write, False to reject.'''
        try:
            watts_int = int(watts)
        except (TypeError, ValueError):
            logging.warning(f"Rejecting non-numeric PowerLimit write: {watts!r}")
            return False
        if watts_int < 0:
            logging.warning(f"Rejecting negative PowerLimit write: {watts_int}")
            return False
        max_power = self._dbusservice["/Ac/MaxPower"]
        if max_power and watts_int > max_power:
            logging.debug(f"Clamping PowerLimit {watts_int}W to MaxPower {max_power}W")
            watts_int = int(max_power)
        payload = {"serial": self.serial, "limit_type": 0, "limit_value": watts_int}
        url = f"{self.get_opendtu_base_url()}/limit/config"
        try:
            response = self.post_url(url, payload)
        except Exception as error:
            logging.warning(f"Failed to apply power limit: {error}")
            return False
        if response.get("type") != "success":
            logging.warning(f"OpenDTU rejected limit: {response}")
            return False
        try:
            self._wait_for_limit_settled()
        except Exception as error:
            logging.warning(f"Post-write limit status refresh failed: {error}")
        return True

    def fetch_ahoy_iv_data(self, inverter_number):
        '''Fetch inverter data from Ahoy device for one inverter'''
        iv_url = self.get_ahoy_base_url() + "/inverter/id/" + str(inverter_number)
        logging.debug(f"Inverter URL: {iv_url}")
        return self.fetch_url(iv_url)

    def fetch_ahoy_record_data(self):
        '''Fetch record data from Ahoy device'''
        record_live_url = self.get_ahoy_base_url() + "/record/live"
        return self.fetch_url(record_live_url)

    @timeit
    def fetch_url(self, url, try_number=1):
        '''Fetch JSON data from url. Throw an exception on any error. Only return on success.'''
        try:
            logging.debug(f"calling {url} with timeout={self.httptimeout}")
            if self.digestauth:
                logging.debug("using Digest access authentication...")
                json_str = requests.get(url=url, auth=HTTPDigestAuth(
                    self.username, self.password), timeout=float(self.httptimeout))
            elif self.username and self.password:
                logging.debug("using Basic access authentication...")
                json_str = requests.get(url=url, auth=(
                    self.username, self.password), timeout=float(self.httptimeout))
            else:
                json_str = requests.get(
                    url=url, timeout=float(self.httptimeout))
            json_str.raise_for_status()  # raise exception on bad status code

            # check for response
            if not json_str:
                logging.info("No Response from DTU")
                raise ConnectionError("No response from DTU - ", self.host)

            json = None
            try:
                json = json_str.json()
            except json.decoder.JSONDecodeError as error:
                logging.debug(f"JSONDecodeError: {str(error)}")

            # check for Json
            if not json:
                # will be logged when catched
                raise ValueError(f"Converting response from {url} to JSON failed: "
                                 f"status={json_str.status_code},\nresponse={json_str.text}")
            return json
        except Exception:
            # retry same call up to MaxFetchTries times
            if try_number < self.max_fetch_tries:  # pylint: disable=no-else-return
                time.sleep(0.5)
                return self.fetch_url(url, try_number + 1)
            else:
                raise

    def post_url(self, url, payload):
        '''POST payload to url wrapped as form field data=<json>. Return parsed JSON response.'''
        form = {"data": json_dumps(payload)}
        logging.debug(f"POST {url} with payload={payload}")
        if self.digestauth:
            response = requests.post(url=url, data=form, auth=HTTPDigestAuth(
                self.username, self.password), timeout=float(self.httptimeout))
        elif self.username and self.password:
            response = requests.post(url=url, data=form, auth=(
                self.username, self.password), timeout=float(self.httptimeout))
        else:
            response = requests.post(url=url, data=form, timeout=float(self.httptimeout))
        response.raise_for_status()
        return response.json()

    def _get_data(self) -> dict:
        if self._test_meter_data:
            return self._test_meter_data
        if not DbusService._meter_data:
            self._refresh_data()

        if self.dtuvariant == constants.DTUVARIANT_TEMPLATE:
            return self.meter_data

        return DbusService._meter_data

    def set_test_data(self, test_data):
        '''Set Test Data to run test'''
        self._test_meter_data = test_data

    def set_dtu_variant(self, dtuvariant):
        '''set DTU variant'''
        self.dtuvariant = dtuvariant

    def is_data_up2date(self):
        '''check if data is up to date with timestamp and producing inverter'''
        if self.max_age_ts < 0:
            # check is disabled by config
            return True

        meter_data = self._get_data()

        if self.dtuvariant == constants.DTUVARIANT_AHOY:
            ts_last_success = self.get_ts_last_success(meter_data)
            age_seconds = time.time() - ts_last_success
            logging.debug("is_data_up2date: inverter #%d: age_seconds=%d, max_age_ts=%d",
                          self.pvinverternumber, age_seconds, self.max_age_ts)
            return 0 <= age_seconds < self.max_age_ts

        if self.dtuvariant == constants.DTUVARIANT_OPENDTU:
            return is_true(meter_data["inverters"][self.pvinverternumber]["reachable"])
        return True

    def _compute_status_code(self):
        '''Map inverter reachable/producing state onto STATUSCODE_* (7/8/10).
           OpenDTU reachable=false means the HTTP fetch succeeded but the
           inverter itself is silent (typically night) -> Standby, not Error.
           HTTP-failure paths still flag Error via set_dbus_values_to_zero().'''
        try:
            meter_data = self._get_data()
            if self.dtuvariant == constants.DTUVARIANT_OPENDTU:
                inv = meter_data["inverters"][self.pvinverternumber]
                if not is_true(inv.get("reachable")):
                    return constants.STATUSCODE_STANDBY
                if is_true(inv.get("producing")):
                    return constants.STATUSCODE_RUNNING
                return constants.STATUSCODE_STANDBY
            if not self.is_data_up2date():
                return constants.STATUSCODE_ERROR
            if self.dtuvariant == constants.DTUVARIANT_AHOY:
                power = get_ahoy_field_by_name(meter_data, self.pvinverternumber, "P_AC")
                if power and float(power) > 0:
                    return constants.STATUSCODE_RUNNING
                return constants.STATUSCODE_STANDBY
            # TEMPLATE: best-effort; assume running when data is up to date
            return constants.STATUSCODE_RUNNING
        except Exception as error:
            logging.debug(f"_compute_status_code fallback to ERROR: {error}")
            return constants.STATUSCODE_ERROR

    def get_ts_last_success(self, meter_data):
        '''return ts_last_success from the meter_data structure - depending on the API version'''
        return meter_data["inverter"][self.pvinverternumber]["ts_last_success"]

    def sign_of_life(self):
        """
        Logs the last update time and the AC power value of the inverter.

        This method logs a debug message with the last update time of the inverter
        and an info message with the AC power value of the inverter.

        Returns:
            bool: Always returns True.
        """
        logging.debug("Last inverter #%d _update() call: %s", self.pvinverternumber, self._last_update)
        logging.info("[%s] Last inverter #%d '/Ac/Power': %s", self._servicename,
                     self.pvinverternumber, self._dbusservice["/Ac/Power"])
        return True

    def _refresh_and_update(self):
        """
        Refresh data and publish it regardless of reachability/age. When the inverter
        is offline (OpenDTU reachable=false, or Ahoy data older than max_age_ts)
        we still want cumulative values (Energy/Forward) on DBus and /StatusCode
        set to ERROR via _compute_status_code.
        """
        self._refresh_data()
        self._publish_connected()
        self._handle_data_update()
        self._update_index()
        return True

    def _publish_connected(self):
        '''OpenDTU only: re-fetch devinfo and publish /Connected = 1 iff both
           devinfo.valid_data and the livedata inverter.reachable flag are true.
           self.devinfo is kept current so hardware metadata survives transient errors
           (we only overwrite it on a successful fetch).'''
        if self.dtuvariant != constants.DTUVARIANT_OPENDTU:
            return
        devinfo = self._fetch_devinfo_safe()
        if devinfo is not None:
            self.devinfo = devinfo
        valid = is_true(self.devinfo.get("valid_data")) if self.devinfo else False
        reachable = False
        try:
            meter_data = self._get_data()
            reachable = is_true(meter_data["inverters"][self.pvinverternumber].get("reachable"))
        except Exception as error:
            logging.debug(f"reachable lookup failed: {error}")
        self._dbusservice["/Connected"] = int(valid and reachable)

    def update(self):
        """
        Updates inverter data from the DTU (Data Transfer Unit) and sets DBus values if the data is up-to-date.

        Main logic:
        - In timeout mode: Always attempt reconnect every RetryAfterSeconds. Only set zero values after ErrorStateAfterSeconds has elapsed since last success.
        - In retrycount mode: After min_retries_until_fail failures, wait RetryAfterSeconds before next attempt and set zero values immediately.
        - Always updates the DBus update index after a refresh.
        - Tracks success/failure state and manages reconnect timing.

        Exception handling:
        - Catches and logs HTTP, value, and general exceptions during update.
        - Ensures update state is finalized regardless of outcome.

        Returns:
            None
        """
        logging.debug("_update")
        successful = False
        now = time.time()
        try:
            if self.error_mode == constants.MODE_TIMEOUT and self.error_state_after_seconds > 0:
                # Set zero values only after ErrorStateAfterSeconds has elapsed since last success
                if (not self.last_update_successful and (now - self._last_update) >= self.error_state_after_seconds):
                    self._handle_reconnect_wait()
                # Always allow a reconnect attempt every RetryAfterSeconds
                if (now - self._last_update) >= self.retry_after_seconds:
                    successful = self._refresh_and_update()
                # In normal operation (no error), always call _refresh_data on every update
                if self.last_update_successful:
                    successful = self._refresh_and_update()
            elif self.error_mode == constants.MODE_RETRYCOUNT:
                # Classic retry-count-based error handling
                if self.failed_update_count >= self.min_retries_until_fail:
                    self._handle_reconnect_wait()
                # Determine if we should refresh data based on current state and timing
                is_last_update_successful = self.last_update_successful
                time_since_last_update = now - self._last_update
                is_retry_interval_elapsed = time_since_last_update >= self.retry_after_seconds
                is_below_min_retries = self.failed_update_count < self.min_retries_until_fail

                should_refresh_data = (
                    is_last_update_successful or
                    is_retry_interval_elapsed or
                    is_below_min_retries
                )

                if should_refresh_data:
                    successful = self._refresh_and_update()
        except requests.exceptions.RequestException as exception:
            logging.warning(f"HTTP Error at _update for inverter "
                            f"{self.pvinverternumber} ({self._get_name()}): {str(exception)}")
        except ValueError as error:
            logging.warning(f"Error at _update for inverter "
                            f"{self.pvinverternumber} ({self._get_name()}): {str(error)}")
        except Exception as error:  # pylint: disable=broad-except
            logging.warning(f"Error at _update for inverter "
                            f"{self.pvinverternumber} ({self._get_name()})", exc_info=error)
        finally:
            self._finalize_update(successful)

    def _handle_reconnect_wait(self):
        if not self.reset_statuscode_on_next_success:
            self.set_dbus_values_to_zero()
            self.reset_statuscode_on_next_success = True

    def _should_refresh_data(self, now):
        return (
            self.last_update_successful or
            (now - self._last_update) >= self.retry_after_seconds or
            self.failed_update_count < self.min_retries_until_fail
        )

    def _handle_data_update(self):
        if self.dry_run:
            logging.info("DRY RUN. No data is sent!!")
        else:
            self.set_dbus_values()

    def _finalize_update(self, successful):
        if successful:
            if self.reset_statuscode_on_next_success:
                self._dbusservice["/StatusCode"] = self._compute_status_code()
            if not self.last_update_successful:
                logging.warning(
                    f"Recovered inverter {self.pvinverternumber} ({self._get_name()}): "
                    f"Successfully fetched data now: "
                    f"{'NOT (yet?)' if not self.is_data_up2date() else 'Is'} up-to-date"
                )
            self.last_update_successful = True
            self.failed_update_count = 0
            self.reset_statuscode_on_next_success = False
        else:
            self.last_update_successful = False
            self.failed_update_count += 1

    def _update_index(self):
        if self.dry_run:
            return
        # increment UpdateIndex - to show that new data is available
        index = self._dbusservice["/UpdateIndex"] + 1  # increment index
        if index > 255:  # maximum value of the index
            index = 0  # overflow from 255 to 0
        self._dbusservice["/UpdateIndex"] = index
        self._last_update = time.time()

    def get_values_for_inverter(self):
        '''read data and return (power, pvyield, current, voltage, dc-voltage)'''
        meter_data = self._get_data()
        (power, pvyield, current, voltage, dc_voltage) = (None, None, None, None, None)

        if self.dtuvariant == constants.DTUVARIANT_AHOY:
            power = get_ahoy_field_by_name(meter_data, self.pvinverternumber, "P_AC")
            if self.useyieldday:
                pvyield = get_ahoy_field_by_name(meter_data, self.pvinverternumber, "YieldDay") / 1000
            else:
                pvyield = get_ahoy_field_by_name(meter_data, self.pvinverternumber, "YieldTotal")
            voltage = get_ahoy_field_by_name(meter_data, self.pvinverternumber, "U_AC")
            dc_voltage = get_ahoy_field_by_name(meter_data, self.pvinverternumber, "U_DC", False)
            current = get_ahoy_field_by_name(meter_data, self.pvinverternumber, "I_AC")

        elif self.dtuvariant == constants.DTUVARIANT_OPENDTU:
            # OpenDTU v24.2.12 breaking API changes 2024-02-19
            if "AC" in meter_data["inverters"][self.pvinverternumber]:
                root_meter_data = meter_data["inverters"][self.pvinverternumber]
                firmware_v24_2_12_or_newer = True
            else:
                inverter_serial = meter_data["inverters"][self.pvinverternumber]["serial"]
                logging.debug(f"Inverter #{self.pvinverternumber} Serial: {inverter_serial}")
                root_meter_data = self.fetch_opendtu_iv_data(inverter_serial)["inverters"][0]
                logging.debug(f"{root_meter_data}")
                firmware_v24_2_12_or_newer = False

            producing = is_true(root_meter_data["producing"])
            power = (root_meter_data["AC"]["0"]["Power"]["v"]
                     if producing
                     else 0)
            field_inv = "AC" if firmware_v24_2_12_or_newer else "INV"
            if self.useyieldday:
                pvyield = root_meter_data[field_inv]["0"]["YieldDay"]["v"] / 1000
            else:
                pvyield = root_meter_data[field_inv]["0"]["YieldTotal"]["v"]
            voltage = root_meter_data["AC"]["0"]["Voltage"]["v"]
            dc_voltage = root_meter_data["DC"]["0"]["Voltage"]["v"]
            current = (root_meter_data["AC"]["0"]["Current"]["v"]
                       if producing
                       else 0)

        elif self.dtuvariant == constants.DTUVARIANT_TEMPLATE:
            power = self.get_processed_meter_value(
                meter_data, self.custpower, self.custpower_default, self.custpower_factor)
            pvyield = self.get_processed_meter_value(
                meter_data, self.custtotal, self.custtotal_default, self.custtotal_factor)
            voltage = self.get_processed_meter_value(meter_data, self.custvoltage, self.custvoltage_default)
            current = self.get_processed_meter_value(meter_data, self.custcurrent, self.custcurrent_default)

        return (power, pvyield, current, voltage, dc_voltage)

    def set_dbus_values_to_zero(self):
        '''zero power data and cleat connection status and set dbus values'''

        if self._servicename == "com.victronenergy.inverter":
            # see https://github.com/victronenergy/venus/wiki/dbus#inverter
            self._dbusservice["/Ac/Out/L1/V"] = 0
            self._dbusservice["/Ac/Out/L1/I"] = 0
            self._dbusservice["/Ac/Out/L1/P"] = 0
            self._dbusservice["/Dc/0/Voltage"] = 0
            self._dbusservice["/Ac/Power"] = 0

            self._dbusservice["/Ac/L1/Current"] = 0
            self._dbusservice["/Ac/L1/Power"] = 0
            self._dbusservice["/Ac/L1/Voltage"] = 0
        else:
            # 0=Startup 0; 1=Startup 1; 2=Startup 2; 3=Startup 3; 4=Startup 4; 5=Startup 5; 6=Startup 6; 7=Running; 8=Standby; 9=Boot loading; 10=Error
            self._dbusservice["/StatusCode"] = constants.STATUSCODE_ERROR

            # three-phase inverter: split total power equally over all three phases
            if "3P" == self.pvinverterphase:

                self._dbusservice["/Ac/L1/Voltage"] = 0
                self._dbusservice["/Ac/L1/Current"] = 0
                self._dbusservice["/Ac/L1/Power"] = 0
                self._dbusservice["/Ac/L2/Voltage"] = 0
                self._dbusservice["/Ac/L2/Current"] = 0
                self._dbusservice["/Ac/L2/Power"] = 0
                self._dbusservice["/Ac/L3/Voltage"] = 0
                self._dbusservice["/Ac/L3/Current"] = 0
                self._dbusservice["/Ac/L3/Power"] = 0
                self._dbusservice["/Ac/Power"] = 0

            else:
                pre = "/Ac/" + self.pvinverterphase
                self._dbusservice[pre + "/Voltage"] = 0
                self._dbusservice[pre + "/Current"] = 0
                self._dbusservice[pre + "/Power"] = 0
                self._dbusservice["/Ac/Power"] = 0

    def set_dbus_values(self):
        '''read data and set dbus values'''
        (power, pvyield, current, voltage, dc_voltage) = self.get_values_for_inverter()
        state = self.get_ac_inverter_state(current)

        if self._servicename == "com.victronenergy.inverter":
            # see https://github.com/victronenergy/venus/wiki/dbus#inverter
            self._dbusservice["/Ac/Out/L1/V"] = voltage
            self._dbusservice["/Ac/Out/L1/I"] = current
            self._dbusservice["/Ac/Out/L1/P"] = power
            self._dbusservice["/Dc/0/Voltage"] = dc_voltage
            self._dbusservice["/Ac/Power"] = power

            self._dbusservice["/Ac/Energy/Forward"] = pvyield
            self._dbusservice["/State"] = state
            self._dbusservice["/Mode"] = 2  # Switch position: 2=Inverter on; 4=Off; 5=Low Power/ECO

            self._dbusservice["/Ac/L1/Current"] = current
            self._dbusservice["/Ac/L1/Energy/Forward"] = pvyield
            self._dbusservice["/Ac/L1/Power"] = power
            self._dbusservice["/Ac/L1/Voltage"] = voltage

            logging.debug(f"Inverter #{self.pvinverternumber} Voltage (/Ac/Out/L1/V): {voltage}")
            logging.debug(f"Inverter #{self.pvinverternumber} Current (/Ac/Out/L1/I): {current}")

            logging.debug(f"Inverter #{self.pvinverternumber} Current (/Dc/0/Voltage): {dc_voltage}")
            logging.debug(f"Inverter #{self.pvinverternumber} Voltage (/Ac/Power): {power}")
            logging.debug(f"Inverter #{self.pvinverternumber} Current (/Ac/Energy/Forward): {pvyield}")
            logging.debug(f"Inverter #{self.pvinverternumber} Current (/State): {state}")
            logging.debug("---")
        else:
            # three-phase inverter: split total power equally over all three phases
            if "3P" == self.pvinverterphase:
                powerthird = power/3

                # Single Phase Voltage = (3-Phase Voltage) / (sqrt(3))
                # This formula assumes that the three-phase voltage is balanced and that
                # the phase angles are 120 degrees apart
                # sqrt(3) = 1.73205080757 <-- So we do not need to include Math Library
                singlePhaseVoltage = voltage / 1.73205080757
                if self.dtuvariant == constants.DTUVARIANT_AHOY:
                    singlePhaseVoltage = voltage
                    self._dbusservice["/Ac/Power"] = power

                realCurrent = power / 3 / singlePhaseVoltage

                self._dbusservice["/Ac/L1/Voltage"] = singlePhaseVoltage
                self._dbusservice["/Ac/L1/Current"] = realCurrent
                self._dbusservice["/Ac/L1/Power"] = powerthird
                self._dbusservice["/Ac/L2/Voltage"] = singlePhaseVoltage
                self._dbusservice["/Ac/L2/Current"] = realCurrent
                self._dbusservice["/Ac/L2/Power"] = powerthird
                self._dbusservice["/Ac/L3/Voltage"] = singlePhaseVoltage
                self._dbusservice["/Ac/L3/Current"] = realCurrent
                self._dbusservice["/Ac/L3/Power"] = powerthird
                self._dbusservice["/Ac/Power"] = power

                # Energy/Forward is cumulative; publish every cycle so totals stay visible
                # while the inverter is offline (e.g. at night).
                if pvyield is not None:
                    self._dbusservice["/Ac/L1/Energy/Forward"] = pvyield / 3
                    self._dbusservice["/Ac/L2/Energy/Forward"] = pvyield / 3
                    self._dbusservice["/Ac/L3/Energy/Forward"] = pvyield / 3
                    self._dbusservice["/Ac/Energy/Forward"] = pvyield

            else:
                pre = "/Ac/" + self.pvinverterphase
                self._dbusservice[pre + "/Voltage"] = voltage
                self._dbusservice[pre + "/Current"] = current
                self._dbusservice[pre + "/Power"] = power
                self._dbusservice["/Ac/Power"] = power
                if pvyield is not None:
                    self._dbusservice[pre + "/Energy/Forward"] = pvyield
                    self._dbusservice["/Ac/Energy/Forward"] = pvyield

            logging.debug(f"Inverter #{self.pvinverternumber} Power (/Ac/Power): {power}")
            logging.debug(f"Inverter #{self.pvinverternumber} Energy (/Ac/Energy/Forward): {pvyield}")
            logging.debug("---")

        self._dbusservice["/StatusCode"] = self._compute_status_code()
