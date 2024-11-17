''' This file contains the unit tests for the DbusService class. '''

import unittest
from unittest.mock import patch, MagicMock, Mock
from dbus_service import DbusService
import requests


def mocked_requests_get(url, params=None, **kwargs):
    """ hiouj"""
    class MockResponse:
        def __init__(self, json_data, status_code):
            self.json_data = json_data
            self.status_code = status_code

        def json(self):
            return self.json_data

        def raise_for_status(self):
            if self.status_code != 200:
                raise requests.exceptions.HTTPError(f"{self.status_code} Error")

    if url == 'http://localhost/api/live':
        return MockResponse({"key1": "value1"}, 200)
    elif url == 'http://someotherurl.com/anothertest.json':
        return MockResponse({"key2": "value2"}, 200)

    return MockResponse(None, 404)


class TestDbusService(unittest.TestCase):

    @patch('dbus_service.VeDbusService')
    @patch('dbus_service.dbus')
    @patch('dbus_service.logging')
    @patch('dbus_service.constants')
    @patch('dbus_service.platform')
    @patch('dbus_service.os')
    def test_init_testing(self, mock_os, mock_platform, mock_constants, mock_logging, mock_dbus, mock_VeDbusService):
        # Test the initialization with servicename "testing"
        servicename = "testing"
        actual_inverter = 1
        istemplate = False

        service = DbusService(servicename, actual_inverter, istemplate)

        self.assertEqual(service.max_age_ts, 600)
        self.assertEqual(service.pvinverternumber, actual_inverter)
        self.assertFalse(service.useyieldday)

    myconfig = {
        "DEFAULT": {
            "DTU": "ahoy",
        },
        "INVERTER0": {
            "Phase": "L1",
            "DeviceInstance": "34",
            "AcPosition": "1",
            "Host": "localhost",
        }
    }

    @patch('dbus_service.DbusService._get_config', return_value=myconfig)
    @patch('dbus_service.dbus')
    @patch('dbus_service.logging')
    @patch('dbus_service.requests.get', side_effect=mocked_requests_get)
    def test_init_non_template(self, mock__get_config, mock_dbus, mock_logging, mock_get):
        """ Test fetch_url with custom responses for different URLs """

        servicename = "com.victronenergy.pvinverter"
        actual_inverter = 0
        istemplate = False

        # Initialize the DbusService

        # with self.assertRaises(ValueError):
        service = DbusService(servicename, actual_inverter, istemplate)

        # Assertions to verify the behavior
        self.assertEqual(service.dtuvariant, "ahoy")

    @patch('dbus_service.VeDbusService')
    @patch('dbus_service.dbus')
    @patch('dbus_service.logging')
    @patch('dbus_service.constants')
    @patch('dbus_service.platform')
    @patch('dbus_service.os')
    def test_init_template(self, mock_os, mock_platform, mock_constants, mock_logging, mock_dbus, mock_VeDbusService):
        # Test the initialization with template servicename
        servicename = "com.victronenergy.inverter"
        actual_inverter = 1
        istemplate = True

        mock_os.environ = {}
        mock_constants.VICTRON_PATHS = {}
        mock_constants.CONNECTION = "connection"
        mock_constants.PRODUCTNAME = "productname"

        service = DbusService(servicename, actual_inverter, istemplate)

        self.assertEqual(service._servicename, servicename)
        self.assertEqual(service.pvinverternumber, actual_inverter)
        self.assertFalse(service.last_update_successful)
        self.assertIsNotNone(service._dbusservice)


if __name__ == '__main__':
    unittest.main()
