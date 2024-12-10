''' This file contains the unit tests for the helper functions in the helpers.py file. '''

# file ignores
# pylint: disable=too-many-instance-attributes

import sys
import os
import unittest
from unittest.mock import MagicMock
import json

# Add the parent directory of dbus_opendtu to the system path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))  # noqa pylint: disable=wrong-import-position

from helpers import (
    get_config_value,
    get_default_config,
    get_value_by_path,
    convert_to_expected_type,
    get_ahoy_field_by_name,
    is_true,
    timeit,
    _kwh,
    _a,
    _w,
    _v,
)
sys.modules['vedbus'] = MagicMock()
sys.modules['dbus'] = MagicMock()
sys.modules['gi.repository'] = MagicMock()
sys.modules['requests'] = MagicMock()
sys.modules['requests.auth'] = MagicMock()

import dbus_service  # noqa pylint: disable=wrong-import-position

# region Helper functions


def get_ahoy_meterdata(filename):
    ''' Load the meter data from the json file. '''
    with open(filename, encoding="utf-8") as file_json:
        json_meter_data = json.load(file_json)

    # add the field "inverter" to meter_data:
    # This will contain an array of the "iv" data from all inverters.
    json_meter_data["inverter"] = []
    for inverter_number in range(len(json_meter_data["iv"])):
        if is_true(json_meter_data["iv"][inverter_number]):
            iv_data = fetch_ahoy_iv_data(inverter_number)
            while len(json_meter_data["inverter"]) < inverter_number:
                # there was a gap in the sequence of inverter numbers -> fill in a dummy value
                json_meter_data["inverter"].append({})
            json_meter_data["inverter"].append(iv_data)

    return json_meter_data


def fetch_ahoy_iv_data(inverter_number):
    ''' Load the inverter data from the json file. '''
    filename = f"./docs/ahoy_0.5.93_inverter-id-{inverter_number}.json"
    # Check if the file exists, otherwise return an empty dict.
    if not os.path.isfile(filename):
        return {}
    with open(filename, encoding="utf-8") as file_json:
        data = json.load(file_json)
    return data


# Load the meter data from the json file.
meter_data_ahoy = get_ahoy_meterdata(filename='./docs/ahoy_0.5.93_live.json')

meter_data = json.loads(
    '{"StatusSNS": {"Time": "2021-02-03T15:12:52", "Switch1": "ON", "ENERGY": '
    '{"TotalStartTime": "2020-01-05T12:41:22", "Total": 13.48712, "Yesterday": 0, '
    '"Today": 0, "Power": 190, "ApparentPower": 0, "ReactivePower": 0, "Factor": 0, '
    '"Voltage": 0, "Current": 0}}}')

meter_data_null = json.loads(
    '{"StatusSNS": {"Time": "2021-02-03T15:12:52", "Switch1": "ON", "ENERGY": '
    '{"TotalStartTime": "2020-01-05T12:41:22", "Total": 13.48712, "Yesterday": 0, '
    '"Today": 0, "Power": null, "ApparentPower": null, "ReactivePower": null, "Factor": null, '
    '"Voltage": 225.66, "Current": null}}}')
# endregion


class TestHelpersFunctions(unittest.TestCase):
    ''' This class contains the unit tests for the helper functions in the helpers.py file. '''

    def setUp(self):
        ''' Setup the test environment. '''
        # Mock the config
        self.config = MagicMock()
        self.config.__getitem__.return_value = {
            "Username": "",
            "Password": "",
            "DigistAuth": "False",
            "CUST_SN": "12345678",
            "CUST_API_PATH": "cm?cmnd=STATUS+8",
            "CUST_POLLING": "2000",
            "CUST_Power": "StatusSNS/ENERGY/Power",
            "CUST_Power_Mult": "1",
            "CUST_Total": "StatusSNS/ENERGY/Total",
            "CUST_Total_Mult": "1",
            "CUST_Voltage": "StatusSNS/ENERGY/Voltage",
            "CUST_Current": "StatusSNS/ENERGY/Current",
            "Phase": "L1",
            "DeviceInstance": "47",
            "AcPosition": "1",
            "Name": "Tasmota",
            "Servicename": "com.victronenergy.grid",
            "DTU": "opendtu",
        }

        self.custpower = self.config["TEMPLATE0"]["CUST_Power"].split("/")
        self.custpower_factor = self.config["TEMPLATE0"]["CUST_Power_Mult"]
        self.custpower_default = get_config_value(self.config, "CUST_Power_Default", "TEMPLATE", 0,  None)
        self.custtotal = self.config["TEMPLATE0"]["CUST_Total"].split("/")
        self.custtotal_factor = self.config["TEMPLATE0"]["CUST_Total_Mult"]
        self.custtotal_default = get_config_value(self.config, "CUST_Total_Default", "TEMPLATE", 0, None)
        self.custvoltage = self.config["TEMPLATE0"]["CUST_Voltage"].split("/")
        self.custvoltage_default = get_config_value(
            self.config, "CUST_Voltage_Default", "TEMPLATE", 0, None)
        self.custcurrent = self.config["TEMPLATE0"]["CUST_Current"].split("/")
        self.custcurrent_default = get_config_value(
            self.config, "CUST_Current_Default", "TEMPLATE", 0)

    def test_get_config_value(self):
        ''' Test the get_config_value() function. '''
        self.assertEqual(get_config_value(self.config, "Phase", "INVERTER", 0), "L1")
        self.assertEqual(get_config_value(self.config, "Username", "TEMPLATE", 0), "")
        self.assertEqual(get_config_value(self.config, "not_exist", "TEMPLATE", 0, "default"), "default")
        with self.assertRaises(ValueError):
            get_config_value(self.config, "not_exist", "INVERTER", 0)

    def test_get_default_config(self):
        ''' Test the get_default_config() function. '''
        self.assertEqual(get_default_config(self.config, "Phase", "L1"), "L1")
        self.assertEqual(get_default_config(self.config, "not_exist", "default"), "default")
        self.assertEqual(get_default_config(self.config, "DTU", "empty"), "opendtu")

    def test_get_value_by_path(self):
        ''' Test the get_nested() function. '''
        self.assertEqual(get_value_by_path(meter_data, self.custpower), 190)
        self.assertEqual(get_value_by_path(meter_data, self.custtotal), 13.48712)
        self.assertEqual(get_value_by_path(meter_data, ["StatusSNS", "ENERGY", "not_there"]), 0)
        self.assertEqual(get_value_by_path(meter_data, ["StatusSNS", "Switch1"]), "ON")

    def test_convert_to_expected_type(self):
        ''' Test the convert_to_expected_type() function. '''
        self.assertEqual(convert_to_expected_type("test", str, "default"), "test")
        self.assertEqual(convert_to_expected_type("test", str, None), "test")
        self.assertEqual(convert_to_expected_type("test", int, 0), 0)
        self.assertEqual(convert_to_expected_type("test", int, None), None)
        self.assertEqual(convert_to_expected_type("test", float, 0.0), 0.0)
        self.assertEqual(convert_to_expected_type("test", float, None), None)
        self.assertEqual(convert_to_expected_type("test", bool, False), False)
        self.assertEqual(convert_to_expected_type("1", bool, None), True)
        self.assertEqual(convert_to_expected_type(None, None, None), None)

    def test_get_ahoy_field_by_name(self):
        ''' Test the get_ahoy_field_by_name() function. '''
        self.assertEqual(get_ahoy_field_by_name(meter_data_ahoy, 0, "P_AC"), 223.7)
        self.assertEqual(get_ahoy_field_by_name(meter_data_ahoy, 0, "YieldDay"), 2223)
        self.assertEqual(get_ahoy_field_by_name(meter_data_ahoy, 0, "YieldTotal"), 422.603)
        self.assertEqual(get_ahoy_field_by_name(meter_data_ahoy, 0, "U_AC"), 229.5)
        self.assertEqual(get_ahoy_field_by_name(meter_data_ahoy, 0, "U_DC", False), 33.3)
        self.assertEqual(get_ahoy_field_by_name(meter_data_ahoy, 0, "I_AC"), 0.98)
        self.assertEqual(get_ahoy_field_by_name(meter_data_ahoy, 0, "I_DC", False), 1.75)
        self.assertEqual(get_ahoy_field_by_name(meter_data_ahoy, 0, "P_DC", False), 58.1)

    def test_get_ahoy_gap_in_inverter_sequence(self):
        ''' Test the special case when there is a gap in the sequence of inverters IDs.'''
        meter_data_ahoy_bad_sequence = get_ahoy_meterdata(
            filename='./docs/ahoy_0.7.36_live_gap_in_inverter_sequence.json')
        self.assertEqual(get_ahoy_field_by_name(meter_data_ahoy_bad_sequence, 1, "P_AC"), 223.7)

    def test_is_true(self):
        ''' Test the is_true() function. '''
        self.assertEqual(is_true("1"), True)
        self.assertEqual(is_true("true"), True)
        self.assertEqual(is_true("True"), True)
        self.assertEqual(is_true("TRUE"), True)
        self.assertEqual(is_true("0"), False)
        self.assertEqual(is_true("false"), False)
        self.assertEqual(is_true("False"), False)
        self.assertEqual(is_true("FALSE"), False)
        self.assertEqual(is_true("test"), False)
        self.assertEqual(is_true(""), False)
        self.assertEqual(is_true(None), False)

    def test_timeit(self):
        ''' Test the timeit() function. '''
        @timeit
        def test_function():
            ''' Test function. '''
            return 1

        self.assertEqual(test_function(), 1)

    def test_part_get_values_for_inverts(self):
        ''' Test part of get_values_for_inverter() function, which is in dbus_service 
        but heavily uses functions in helpers.py. '''

        power = dbus_service.DbusService.get_processed_meter_value(
            meter_data_null,
            self.custpower,
            self.custpower_default,
            self.custpower_factor
        )

        pvyield = dbus_service.DbusService.get_processed_meter_value(
            meter_data_null,
            self.custtotal,
            self.custtotal_default,
            self.custtotal_factor
        )

        voltage = dbus_service.DbusService.get_processed_meter_value(
            meter_data_null,
            self.custvoltage,
            self.custpower_default,
        )

        current = dbus_service.DbusService.get_processed_meter_value(
            meter_data_null,
            self.custcurrent,
            self.custpower_default,
        )

        self.assertEqual(power, None)
        self.assertEqual(pvyield, 13.48712)
        self.assertEqual(voltage, 225.66)
        self.assertEqual(current, None)

    def test_kwh(self):
        ''' Test the _kwh() function. '''
        self.assertEqual(_kwh(None, 123.456), "123.46KWh")
        self.assertEqual(_kwh(None, 1.234), "1.23KWh")
        self.assertEqual(_kwh(None, -1.234), "-1.23KWh")
        self.assertEqual(_kwh(None, 0), "0.00KWh")
        self.assertEqual(_kwh(None, 0.1234), "0.12KWh")
        self.assertEqual(_kwh(None, 1.5678), "1.57KWh")

    def test_a(self):
        ''' Test the _a() function. '''
        self.assertEqual(_a(None, 0), "0.0A")
        self.assertEqual(_a(None, 0.45), "0.5A")
        self.assertEqual(_a(None, 0.459), "0.5A")
        self.assertEqual(_a(None, 1.2345), "1.2A")
        self.assertEqual(_a(None, 1.5678), "1.6A")
        self.assertEqual(_a(None, -1.5678), "-1.6A")

    def test_w(self):
        ''' Test the _w() function. '''
        self.assertEqual(_w(None, 0), "0.0W")
        self.assertEqual(_w(None, 0.45), "0.5W")
        self.assertEqual(_w(None, 0.459), "0.5W")
        self.assertEqual(_w(None, 1.2345), "1.2W")
        self.assertEqual(_w(None, 1.5678), "1.6W")
        self.assertEqual(_w(None, -1.5678), "-1.6W")

    def test_v(self):
        ''' Test the _v() function. '''
        self.assertEqual(_v(None, 0), "0.0V")
        self.assertEqual(_v(None, 0.45), "0.5V")
        self.assertEqual(_v(None, 0.459), "0.5V")
        self.assertEqual(_v(None, 1.2345), "1.2V")
        self.assertEqual(_v(None, 1.5678), "1.6V")
        self.assertEqual(_v(None, -1.5678), "-1.6V")


if __name__ == '__main__':
    unittest.main()
