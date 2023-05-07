''' This file contains the unit tests for the helper functions in the helpers.py file. '''

import sys
import unittest
from unittest.mock import MagicMock
import json
from helpers import *
sys.modules['vedbus'] = MagicMock()
sys.modules['dbus'] = MagicMock()
sys.modules['gi.repository'] = MagicMock()

import dbus_service  # noqa pylint: disable=wrong-import-position


class TestHelpersFunctions(unittest.TestCase):
    ''' This class contains the unit tests for the helper functions in the helpers.py file. '''

    def setUp(self):
        ''' Setup the test environment. '''
        # TODO: Create a mock config file and use that instead of the real one.
        self.config = dbus_service.DbusService._get_config()

        self.custpower = self.config["TEMPLATE0"]["CUST_Power"].split("/")
        self.custtotal = self.config["TEMPLATE0"]["CUST_Total"].split("/")

        # Load the meter data from the json file.
        file_json = open('./docs/opendtu_status.json')
        self.meter_data_ahoy = json.load(file_json)
        self.meter_data = json.loads(
            '{"StatusSNS": {"Time": "2021-02-03T15:12:52", "Switch1": "ON", "ENERGY": '
            '{"TotalStartTime": "2020-01-05T12:41:22", "Total": 13.48712, "Yesterday": 0, '
            '"Today": 0, "Power": 190, "ApparentPower": 0, "ReactivePower": 0, "Factor": 0, '
            '"Voltage": 0, "Current": 0}}}')

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
        self.assertEqual(get_nested(self.meter_data, self.custpower), 190)
        self.assertEqual(get_nested(self.meter_data, self.custtotal), 13.48712)
        self.assertEqual(get_nested(self.meter_data, ["StatusSNS", "ENERGY", "not_there"]), 0)
        self.assertEqual(get_nested(self.meter_data, ["StatusSNS", "Switch1"]), "ON")

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

    # def test_get_ahoy_field_by_name(self):
      # assert get_ahoy_field_by_name(self.meter_data, "0", "Power") == 190


if __name__ == '__main__':
    unittest.main()
