'''DbusService and PvInverterRegistry'''

# File specific rules
# pylint: disable=broad-except, import-error, wrong-import-order, wrong-import-position

# system imports:
import configparser
import os
import platform
import sys
import logging
import time
import requests  # for http GET
from requests.auth import HTTPDigestAuth

# our imports:
import constants
from helpers import *

# victron imports:
import dbus

if sys.version_info.major == 2:
    import gobject
else:
    from gi.repository import GLib as gobject

sys.path.insert(
    1,
    os.path.join(
        os.path.dirname(__file__),
        "/opt/victronenergy/dbus-systemcalc-py/ext/velib_python",
    ),
)
from vedbus import VeDbusService  # noqa - must be placed after the sys.path.insert


class PvInverterRegistry(type):
    '''Run a registry for all PV Inverter'''
    def __iter__(cls):
        return iter(cls._registry)


class DbusService:
    '''Main class to register PV Inverter in DBUS'''
    __metaclass__ = PvInverterRegistry
    _registry = []
    _meter_data = None
    _test_meter_data = None
    _servicename = None

    def __init__(
        self,
        servicename,
        paths,
        actual_inverter,
        istemplate=False,
    ):

        # This is (for now) not used elsewhere and is more of a constant
        # than a contstuctor attribute
        productname = "OpenDTU"
        connection = "TCP/IP (HTTP)"

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

        if not istemplate:
            self._read_config_dtu(actual_inverter)
            self.numberofinverters = self.get_number_of_inverters()
        else:
            self._read_config_template(actual_inverter)

        logging.debug("%s /DeviceInstance = %d", servicename, self.deviceinstance)

        # Allow for multiple Instance per process in DBUS
        dbus_conn = (
            dbus.SessionBus()
            if "DBUS_SESSION_BUS_ADDRESS" in os.environ
            else dbus.SystemBus(private=True)
        )

        self._dbusservice = VeDbusService(f"{servicename}.http_{self.deviceinstance}", dbus_conn)
        self._paths = paths

        # Create the management objects, as specified in the ccgx dbus-api document
        self._dbusservice.add_path("/Mgmt/ProcessName", __file__)
        self._dbusservice.add_path("/Mgmt/ProcessVersion",
                                   "Unkown version, and running on Python " + platform.python_version())
        self._dbusservice.add_path("/Mgmt/Connection", connection)

        # Create the mandatory objects
        self._dbusservice.add_path("/DeviceInstance", self.deviceinstance)
        self._dbusservice.add_path("/ProductId", 0xFFFF)  # id assigned by Victron Support from SDM630v2.py
        self._dbusservice.add_path("/ProductName", productname)
        self._dbusservice.add_path("/CustomName", self._get_name())
        logging.info(f"Name of Inverters found: {self._get_name()}")
        self._dbusservice.add_path("/Connected", 1)

        self._dbusservice.add_path("/Latency", None)
        self._dbusservice.add_path("/FirmwareVersion", 0.1)
        self._dbusservice.add_path("/HardwareVersion", 0)
        self._dbusservice.add_path("/Position", self.acposition)  # normaly only needed for pvinverter
        self._dbusservice.add_path("/Serial", self._get_serial(self.pvinverternumber))
        self._dbusservice.add_path("/UpdateIndex", 0)
        self._dbusservice.add_path("/StatusCode", 0)  # Dummy path so VRM detects us as a PV-inverter.

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
        for path, settings in self._paths.items():
            self._dbusservice.add_path(
                path,
                settings["initial"],
                gettextcallback=settings["textformat"],
                writeable=True,
                onchangecallback=self._handlechangedvalue,
            )

        # add _sign_of_life 'timer' to get feedback in log every 5minutes
        gobject.timeout_add(self._get_sign_of_life_interval() * 60 * 1000, self._sign_of_life)

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

    @staticmethod
    def _handlechangedvalue(path, value):
        logging.debug("someone else updated %s to %s", path, value)
        return True  # accept the change

    @staticmethod
    def _get_config():
        config = configparser.ConfigParser()
        config.read(f"{(os.path.dirname(os.path.realpath(__file__)))}/config.ini")
        return config

    @staticmethod
    def get_processed_meter_value(meter_data: dict, value: str, default_value: any, factor: int = 1) -> any:
        '''return the processed meter value by applying the factor and return a default value due an Exception'''
        get_raw_value = get_value_by_path(meter_data, value)
        raw_value = convert_to_expected_type(get_raw_value, float, default_value)
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
                {constants.DTUVARIANT_AHOY}, \
                {constants.DTUVARIANT_TEMPLATE}")
        self.deviceinstance = int(config[f"INVERTER{self.pvinverternumber}"]["DeviceInstance"])
        self.acposition = int(get_config_value(config, "AcPosition", "INVERTER", self.pvinverternumber))
        self.signofliveinterval = get_config_value(config, "SignOfLifeLog", "DEFAULT", "", 1)
        self.useyieldday = int(get_config_value(config, "useYieldDay", "DEFAULT", "", 0))
        self.pvinverterphase = str(config[f"INVERTER{self.pvinverternumber}"]["Phase"])
        self.host = get_config_value(config, "Host", "INVERTER", self.pvinverternumber)
        self.username = get_config_value(config, "Username", "DEFAULT", "", self.pvinverternumber)
        self.password = get_config_value(config, "Password", "DEFAULT", "", self.pvinverternumber)
        self.digestauth = is_true(get_config_value(config, "DigestAuth", "INVERTER", self.pvinverternumber, False))

        try:
            self.max_age_ts = int(config["DEFAULT"]["MaxAgeTsLastSuccess"])
        except (KeyError, ValueError) as ex:
            logging.debug("MaxAgeTsLastSuccess: %s", ex)
            logging.debug("MaxAgeTsLastSuccess not set, using default")
            self.max_age_ts = 600

        self.dry_run = is_true(get_default_config(config, "DryRun", False))
        self.pollinginterval = int(get_config_value(config, "ESP8266PollingIntervall", "DEFAULT", "", 10000))
        self.meter_data = 0
        self.httptimeout = get_default_config(config, "HTTPTimeout", 2.5)

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
        self.signofliveinterval = get_config_value(config, "SignOfLifeLog", "DEFAULT", "", 1)
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
            logging.debug("MaxAgeTsLastSuccess: %s", ex)
            logging.debug("MaxAgeTsLastSuccess not set, using default")
            self.max_age_ts = 600

        self.dry_run = is_true(get_default_config(config, "DryRun", False))
        self.meter_data = 0
        self.httptimeout = get_default_config(config, "HTTPTimeout", 2.5)

    # get the Serialnumber
    def _get_serial(self, pvinverternumber):

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

        gobject.timeout_add(self._get_polling_interval(), self._update)

        return serial

    def _get_name(self):
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
        elif self.dtuvariant == constants.DTUVARIANT_OPENDTU:
            numberofinverters = len(meter_data["inverters"])
        else:
            numberofinverters = 1
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
            polling_interval = 5000

        elif self.dtuvariant == constants.DTUVARIANT_TEMPLATE:
            polling_interval = self.pollinginterval
        return polling_interval

    def _get_sign_of_life_interval(self):
        '''Get intervall in seconds how often sign of life logs should be created.'''
        value = self.signofliveinterval
        if not value:
            value = 0
        return int(value)

    def _get_status_url(self):
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

    def fetch_opendtu_inverter_data(self, inverter_serial):
        '''Fetch inverter date from OpenDTU device for one interter'''
        iv_url = self._get_status_url() + "?inv=" + inverter_serial
        return self.fetch_url(iv_url)

    def fetch_ahoy_iv_data(self, inverter_number):
        '''Fetch inverter date from Ahoy device for one interter'''
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
            # retry same call up to 3 times
            if try_number < 3:  # pylint: disable=no-else-return
                time.sleep(0.5)
                return self.fetch_url(url, try_number + 1)
            else:
                raise

    def _get_data(self):
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

    def get_ts_last_success(self, meter_data):
        '''return ts_last_success from the meter_data structure - depending on the API version'''
        return meter_data["inverter"][self.pvinverternumber]["ts_last_success"]

    def _sign_of_life(self):
        logging.debug("Last inverter #%d _update() call: %s", self.pvinverternumber, self._last_update)
        logging.info("Last inverter #%d '/Ac/Power': %s", self.pvinverternumber, self._dbusservice["/Ac/Power"])
        return True

    def _update(self):
        successful = False
        try:
            # update data from DTU once per _update call:
            self._refresh_data()

            if self.is_data_up2date():
                if self.dry_run:
                    logging.info("DRY RUN. No data is sent!!")
                else:
                    self.set_dbus_values()
            self._update_index()
            successful = True
        except requests.exceptions.RequestException as exception:
            if self.last_update_successful:
                logging.warning(f"HTTP Error at _update for inverter "
                                f"{self.pvinverternumber} ({self._get_name()}): {str(exception)}")
        except ValueError as error:
            if self.last_update_successful:
                logging.warning(f"Error at _update for inverter "
                                f"{self.pvinverternumber} ({self._get_name()}): {str(error)}")
        except Exception as error:  # pylint: disable=broad-except
            if self.last_update_successful:
                logging.warning(f"Error at _update for inverter "
                                f"{self.pvinverternumber} ({self._get_name()})", exc_info=error)
        finally:
            if successful:
                if not self.last_update_successful:
                    logging.warning(
                        f"Recovered inverter {self.pvinverternumber} ({self._get_name()}): "
                        f"Successfully fetched data now: "
                        f"{'NOT (yet?)' if not self.is_data_up2date() else 'Is'} up-to-date"
                    )
                    self.last_update_successful = True
            else:
                self.last_update_successful = False

        # return true, otherwise add_timeout will be removed from GObject - see docs
        # http://library.isr.ist.utl.pt/docs/pygtk2reference/gobject-functions.html#function-gobject--timeout-add
        return True

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
                firmware_v24_2_12_or_newer=True
            else:
                inverter_serial = meter_data["inverters"][self.pvinverternumber]["serial"]
                logging.info(f"Inverter #{self.pvinverternumber} Serial: {inverter_serial}")
                root_meter_data = self.fetch_opendtu_inverter_data(inverter_serial)["inverters"][0]
                logging.debug(f"{root_meter_data}")
                firmware_v24_2_12_or_newer=False

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
            voltage = self.get_processed_meter_value(meter_data, self.custvoltage, self.custpower_default)
            current = self.get_processed_meter_value(meter_data, self.custcurrent, self.custpower_default)

        return (power, pvyield, current, voltage, dc_voltage)

    def set_dbus_values(self):
        '''read data and set dbus values'''
        (power, pvyield, current, voltage, dc_voltage) = self.get_values_for_inverter()

        # This will be refactored later in classes
        if self._servicename == "com.victronenergy.inverter":
            self._dbusservice["/Ac/Out/L1/V"] = voltage
            self._dbusservice["/Ac/Out/L1/I"] = current
            self._dbusservice["/Dc/0/Voltage"] = dc_voltage
            self._dbusservice["/State"] = self.get_ac_inverter_state(current)

            logging.debug(f"Inverter #{self.pvinverternumber} Voltage (/Ac/Out/L1/V): {voltage}")
            logging.debug(f"Inverter #{self.pvinverternumber} Current (/Ac/Out/L1/I): {current}")
            logging.debug("---")
        else:
            # three-phase inverter: split total power equally over all three phases
            if ("3P" == self.pvinverterphase):
                powerthird = power/3

                #Single Phase Voltage = (3-Phase Voltage) / (sqrt(3))
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

                if power > 0:
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
                if power > 0:
                    self._dbusservice[pre + "/Energy/Forward"] = pvyield
                    self._dbusservice["/Ac/Energy/Forward"] = pvyield

            logging.debug(f"Inverter #{self.pvinverternumber} Power (/Ac/Power): {power}")
            logging.debug(f"Inverter #{self.pvinverternumber} Energy (/Ac/Energy/Forward): {pvyield}")
            logging.debug("---")
