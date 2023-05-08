''' This file contains the unit tests for the helper functions in the helpers.py file. '''

import sys
import os
import unittest
from unittest.mock import MagicMock
import json
from helpers import *
sys.modules['vedbus'] = MagicMock()
sys.modules['dbus'] = MagicMock()
sys.modules['gi.repository'] = MagicMock()
sys.modules['requests'] = MagicMock()
sys.modules['requests.auth'] = MagicMock()

import dbus_service  # noqa pylint: disable=wrong-import-position

# region Helper functions


def get_ahoy_meterdata(filename):
    ''' Load the meter data from the json file. '''
    file_json = open(filename, encoding="utf-8")
    json_meter_data = json.load(file_json)
    file_json.close()
    json_meter_data["inverter"] = []
    for inverter_number in range(len(json_meter_data["iv"])):
        if is_true(json_meter_data["iv"][inverter_number]):
            iv_data = fetch_ahoy_iv_data(inverter_number)
            while len(json_meter_data["inverter"]) < inverter_number:
                # there was a gap
                json_meter_data.append({})
            json_meter_data["inverter"].append(iv_data)

    return json_meter_data


def fetch_ahoy_iv_data(inverter_number):
    ''' Load the inverter data from the json file. '''
    filename = f"./docs/ahoy_0.5.93_inverter-id-{inverter_number}.json"
    # Check if the file exists, otherwise return an empty dict.
    if not os.path.isfile(filename):
        return {}
    file_json = open(filename, encoding="utf-8")
    data = json.load(file_json)
    file_json.close()
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
        # TODO: Create a mock config file and use that instead of the real one.
        self.config = dbus_service.DbusService._get_config()

        self.custpower = self.config["TEMPLATE0"]["CUST_Power"].split("/")
        self.custpower_factor = self.config["TEMPLATE0"]["CUST_Power_Mult"]
        self.custpower_default = get_default_template_config(self.config, 0, "CUST_Power_Default", None)
        self.custtotal = self.config["TEMPLATE0"]["CUST_Total"].split("/")
        self.custtotal_factor = self.config["TEMPLATE0"]["CUST_Total_Mult"]
        self.custtotal_default = get_default_template_config(self.config, 0, "CUST_Total_Default", None)
        self.custvoltage = self.config["TEMPLATE0"]["CUST_Voltage"].split("/")
        self.custvoltage_default = get_default_template_config(
            self.config, 0, "CUST_Voltage_Default", None)
        # self.custdcvoltage = self.config["TEMPLATE0"]["CUST_DCVoltage"].split("/")
        # self.custdcvoltage_default = get_default_template_config(
        #     self.config, 0, "CUST_DCVoltage_Default", None)
        self.custcurrent = self.config["TEMPLATE0"]["CUST_Current"].split("/")
        self.custcurrent_default = get_default_template_config(
            self.config, 0, "CUST_Current_Default", None)

    def test_get_config_value(self):
        ''' Test the get_config_value() function. '''
        self.assertEqual(get_config_value(self.config, "Phase", "INVERTER", 0), "L1")
        self.assertEqual(get_config_value(self.config, "Username", "TEMPLATE", 0), "")
        self.assertEqual(get_config_value(self.config, "not_exist", "TEMPLATE", 0, "default"), "default")
        with self.assertRaises(ValueError):
            get_config_value(self.config, "not_exist", "TEMPLATE", 0)

    def test_get_default_config(self):
        ''' Test the get_default_config() function. '''
        self.assertEqual(get_default_config(self.config, "Phase", "L1"), "L1")
        self.assertEqual(get_default_config(self.config, "not_exist", "default"), "default")
        self.assertEqual(get_default_config(self.config, "DTU", "empty"), "opendtu")

    def test_get_nested(self):
        ''' Test the get_nested() function. '''
        self.assertEqual(get_nested(meter_data, self.custpower), 190)
        self.assertEqual(get_nested(meter_data, self.custtotal), 13.48712)
        self.assertEqual(get_nested(meter_data, ["StatusSNS", "ENERGY", "not_there"]), 0)
        self.assertEqual(get_nested(meter_data, ["StatusSNS", "Switch1"]), "ON")

    def test_get_default_template_config(self):
        ''' Test the get_default_template_config() function. '''
        self.assertEqual(get_default_template_config(self.config, 0, "CUST_POLLING"), "2000")
        self.assertEqual(get_default_template_config(self.config, 0, "not_exist", "default"), "default")

    def test_try_get_value(self):
        ''' Test the try_get_value() function. '''
        self.assertEqual(try_get_value("test", str, "default"), "test")
        self.assertEqual(try_get_value("test", str, None), "test")
        self.assertEqual(try_get_value("test", int, 0), 0)
        self.assertEqual(try_get_value("test", int, None), None)
        self.assertEqual(try_get_value("test", float, 0.0), 0.0)
        self.assertEqual(try_get_value("test", float, None), None)
        self.assertEqual(try_get_value("test", bool, False), False)
        self.assertEqual(try_get_value("1", bool, None), True)
        self.assertEqual(try_get_value(None, None, None), None)

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

        get_power = get_nested(meter_data_null, self.custpower)
        power_value = try_get_value(get_power, float, self.custpower_default)
        if isinstance(power_value, float) or isinstance(power_value, int):
            power = float(power_value * float(self.custpower_factor))
        else:
            power = power_value

        get_pv_yield = get_nested(meter_data_null, self.custtotal)
        pvyield_value = try_get_value(get_pv_yield, float, self.custtotal_default)
        if isinstance(pvyield_value, float) or isinstance(pvyield_value, int):
            pvyield = float(pvyield_value * float(self.custtotal_factor))
        else:
            pvyield = pvyield_value

        get_voltage = get_nested(meter_data_null, self.custvoltage)
        voltage_value = try_get_value(get_voltage, float, self.custvoltage_default)
        if isinstance(voltage_value, float) or isinstance(voltage_value, int):
            voltage = float(voltage_value)
        else:
            voltage = voltage_value

        # get_dc_voltage = get_nested(meter_data, self.custdcvoltage)
        # dc_voltage_value = try_get_value(get_dc_voltage, float, self.custdcvoltage_default)
        # dc_voltage = float(dc_voltage_value)
        # print()

        get_current = get_nested(meter_data_null, self.custcurrent)
        current_value = try_get_value(get_current, float, self.custcurrent_default)
        if isinstance(current_value, float) or isinstance(current_value, int):
            current = float(current_value)
        else:
            current = current_value

        self.assertEqual(power, None)
        self.assertEqual(pvyield, 13.48712)
        self.assertEqual(voltage, 225.66)
        self.assertEqual(current, None)


if __name__ == '__main__':
    unittest.main()
