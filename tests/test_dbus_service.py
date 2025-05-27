''' This file contains the unit tests for the DbusService class. '''

import time
import unittest
from unittest.mock import MagicMock, patch
import os
import json
import requests
from dbus_service import DbusService


def mocked_requests_get(url, params=None, **kwargs):  # pylint: disable=unused-argument
    """
    Mock function to simulate `requests.get` behavior for specific URLs.

    Args:
        url (str): The URL to send the GET request to.
        params (dict, optional): Dictionary of URL parameters to append to the URL.
        **kwargs: Additional arguments passed to the request.

    Returns:
        MockResponse: A mock response object with predefined JSON data and status code.

    Raises:
        requests.exceptions.HTTPError: If the status code of the response is not 200.

    Mocked URLs and their corresponding JSON files:
        - 'http://localhost/api/live': Returns data from 'ahoy_0.5.93_live.json'.
        - 'http://localhost/api/inverter/id/0': Returns data from 'ahoy_0.5.93_inverter-id-0.json'.
        - 'http://localhost/api/inverter/id/1': Returns data from 'ahoy_0.5.93_inverter-id-1.json'.
        - 'http://localhost/cm?cmnd=STATUS+8': Returns data from 'tasmota_shelly_2pm.json'.
        - Any other URL: Returns a 404 status code.
    """
    class MockResponse:
        """
        MockResponse is a mock class to simulate HTTP responses for testing purposes.

        Attributes:
            json_data (dict): The JSON data to be returned by the mock response.
            status_code (int): The HTTP status code of the mock response.

        Methods:
            json(): Returns the JSON data of the mock response.
            raise_for_status(): Raises an HTTPError if the status code is not 200.
        """

        def __init__(self, json_data, status_code):
            self.json_data = json_data
            self.status_code = status_code

        def json(self):
            """
            Returns the JSON data.

            Returns:
                dict: The JSON data.
            """
            return self.json_data

        def raise_for_status(self):
            """
            Raises an HTTPError if the HTTP request returned an unsuccessful status code.

            This method checks the status code of the HTTP response. If the status code is not 200,
            it raises an HTTPError with a message containing the status code.

            Raises:
                requests.exceptions.HTTPError: If the status code is not 200.
            """
            if self.status_code != 200:
                raise requests.exceptions.HTTPError(f"{self.status_code} Error")

    print("Mock URL: ", url)

    if url == 'http://localhost/api/live':
        json_file_path = os.path.join(os.path.dirname(__file__), '../docs/ahoy_0.5.93_live.json')
        with open(json_file_path, 'r', encoding="UTF-8") as file:
            json_data = json.load(file)
        return MockResponse(json_data, 200)
    elif url == 'http://localhost/api/inverter/id/0':
        json_file_path = os.path.join(os.path.dirname(__file__), '../docs/ahoy_0.5.93_inverter-id-0.json')
        with open(json_file_path, 'r', encoding="UTF-8") as file:
            json_data = json.load(file)
        return MockResponse(json_data, 200)
    elif url == 'http://localhost/api/inverter/id/1':
        json_file_path = os.path.join(os.path.dirname(__file__), '../docs/ahoy_0.5.93_inverter-id-1.json')
        with open(json_file_path, 'r', encoding="UTF-8") as file:
            json_data = json.load(file)
        return MockResponse(json_data, 200)
    elif url == 'http://localhost/cm?cmnd=STATUS+8':
        json_file_path = os.path.join(os.path.dirname(__file__), '../docs/tasmota_shelly_2pm.json')
        with open(json_file_path, 'r', encoding="UTF-8") as file:
            json_data = json.load(file)
        return MockResponse(json_data, 200)
    elif url == 'http://localhost/api/livedata/status':
        json_file_path = os.path.join(os.path.dirname(__file__), '../docs/opendtu_v24.2.12_livedata_status.json')
        with open(json_file_path, 'r', encoding="UTF-8") as file:
            json_data = json.load(file)
        return MockResponse(json_data, 200)
    return MockResponse(None, 404)


class TestDbusService(unittest.TestCase):
    """ Test the DbusService class """

    @patch('dbus_service.dbus')
    def test_init_testing(self, _mock_dbus):
        """ Test the initialization of the DbusService class """
        servicename = "Nuclear_plant"
        actual_inverter = -1
        istemplate = False

        with self.assertRaises(KeyError):
            DbusService(servicename, actual_inverter, istemplate)

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

        DbusService._meter_data = None
        servicename = "com.victronenergy.pvinverter"
        actual_inverter = 0
        istemplate = False

        # Initialize the DbusService

        # with self.assertRaises(ValueError):
        service = DbusService(servicename, actual_inverter, istemplate)

        # Assertions to verify the behavior
        self.assertEqual(service.dtuvariant, "ahoy")

    config_for_test_if_number_of_inverters_are_set = {
        "DEFAULT": {
            "DTU": "ahoy",
        },
        "INVERTER0": {
            "Phase": "L1",
            "DeviceInstance": "34",
            "AcPosition": "1",
            "Host": "localhost",
        },
    }

    @patch('dbus_service.DbusService._get_config', return_value=config_for_test_if_number_of_inverters_are_set)
    @patch('dbus_service.dbus')
    @patch('dbus_service.logging')
    @patch('dbus_service.requests.get', side_effect=mocked_requests_get)
    def test_if_number_of_inverters_are_set(self, mock__get_config, mock_dbus, mock_logging, mock_get):
        """ Test fetch_url with custom responses for different URLs """

        servicename = "com.victronenergy.pvinverter"
        actual_inverter = 0
        istemplate = False

        service = DbusService(servicename, actual_inverter, istemplate)

        self.assertEqual(service.dtuvariant, "ahoy")
        self.assertEqual(service.get_number_of_inverters(), 2)

    config_for_test_if_number_of_inverters_are_set_opendtu = {
        "DEFAULT": {
            "DTU": "opendtu",
        },
        "INVERTER0": {
            "Phase": "L1",
            "DeviceInstance": "34",
            "AcPosition": "1",
            "Host": "localhost",
        },
    }

    @patch('dbus_service.DbusService._get_config', return_value=config_for_test_if_number_of_inverters_are_set_opendtu)
    @patch('dbus_service.dbus')
    @patch('dbus_service.logging')
    @patch('dbus_service.requests.get', side_effect=mocked_requests_get)
    def test_if_number_of_inverters_are_set_opendtu(self, mock__get_config, mock_dbus, mock_logging, mock_get):
        """ Test fetch_url with custom responses for different URLs """

        DbusService._meter_data = None
        servicename = "com.victronenergy.pvinverter"
        actual_inverter = 0
        istemplate = False

        service = DbusService(servicename, actual_inverter, istemplate)

        self.assertEqual(service.dtuvariant, "opendtu")
        self.assertEqual(service.get_number_of_inverters(), 2)

    template_config = {
        "DEFAULT": {
            "DTU": "ahoy",
        },
        "TEMPLATE0": {
            "Username": "",
            "Password": "",
            "DigestAuth": "False",
            "Host": "localhost",
            "CUST_SN": "12345678",
            "CUST_API_PATH": "cm?cmnd=STATUS+8",
            "CUST_POLLING": "2000",
            "CUST_Total": "StatusSNS/ENERGY/Total",
            "CUST_Total_Mult": "1",
            "CUST_Power": "StatusSNS/ENERGY/Power",
            "CUST_Power_Mult": "1",
            "CUST_Voltage": "StatusSNS/ENERGY/Voltage",
            "CUST_Current": "StatusSNS/ENERGY/Current",
            "Phase": "L1",
            "DeviceInstance": "47",
            "AcPosition": "1",
            "Name": "Tasmota",
            "Servicename": "com.victronenergy.grid"
        }
    }

    @patch('dbus_service.DbusService._get_config', return_value=template_config)
    @patch('dbus_service.dbus')
    @patch('dbus_service.logging')
    @patch('dbus_service.requests.get', side_effect=mocked_requests_get)
    def test_init_template(self,  mock__get_config, mock_dbus,  mock_logging, mock_get):
        # Test the initialization with template servicename
        servicename = "com.victronenergy.inverter"
        actual_inverter = 0
        istemplate = True

        service = DbusService(servicename, actual_inverter, istemplate)

        self.assertEqual(service._servicename, servicename)
        self.assertEqual(service.pvinverternumber, actual_inverter)
        self.assertFalse(service.last_update_successful)
        self.assertIsNotNone(service._dbusservice)


class ReconnectLogicTest(unittest.TestCase):
    def setUp(self):
        # Set up all required patches and a default DbusService instance for each test
        self.patcher_config = patch('dbus_service.DbusService._get_config', return_value={
            "DEFAULT": {"DTU": "ahoy", "ReconnectAfter": "10"},
            "INVERTER0": {"Phase": "L1", "DeviceInstance": "34", "AcPosition": "1", "Host": "localhost"},
        })
        self.patcher_dbus = patch('dbus_service.dbus')
        self.patcher_logging = patch('dbus_service.logging')
        self.patcher_requests = patch('dbus_service.requests.get', side_effect=mocked_requests_get)
        self.mock_config = self.patcher_config.start()
        self.mock_dbus = self.patcher_dbus.start()
        self.mock_logging = self.patcher_logging.start()
        self.mock_requests = self.patcher_requests.start()
        self.addCleanup(self.patcher_config.stop)
        self.addCleanup(self.patcher_dbus.stop)
        self.addCleanup(self.patcher_logging.stop)
        self.addCleanup(self.patcher_requests.stop)

        self.service = DbusService("com.victronenergy.pvinverter", 0)
        self.service._refresh_data = MagicMock()
        self.service.is_data_up2date = MagicMock(return_value=False)
        self.service.set_dbus_values = MagicMock()
        self.service._update_index = MagicMock()
        self.service.dry_run = True
        self.service.retryAfterSeconds = 300  # seconds
        self.service._last_update = time.time() - 100

        # Simulate a dbusservice dict for status and value tests
        self.service._dbusservice = {k: 1 for k in [
            '/StatusCode', '/Ac/Out/L1/V', '/Ac/Out/L1/I', '/Ac/Out/L1/P', '/Dc/0/Voltage', '/Ac/Power',
            '/Ac/L1/Current', '/Ac/L1/Energy/Forward', '/Ac/L1/Power', '/Ac/L1/Voltage']}

    def test_failed_update_count_increments(self):
        """Test that failed_update_count increases after consecutive failed updates (exceptions)."""
        self.service._refresh_data.side_effect = requests.exceptions.RequestException("Test exception")
        for _ in range(3):
            self.service.last_update_successful = False
            self.service.update()
        self.assertEqual(self.service.failed_update_count, 3)
        self.service._refresh_data.side_effect = None

    def test_reconnect_pause_after_3_failures(self):
        """Test that after 3 failures, update() does not call _refresh_data if reconnectAfter time is not over."""
        self.service.failed_update_count = 3
        self.service.last_update_successful = False
        self.service._last_update = time.time() - (4 * 60)  # less than reconnectAfter
        self.service._refresh_data.reset_mock()
        self.service.update()
        self.service._refresh_data.assert_not_called()

    def test_update_allowed_after_reconnect_pause(self):
        """Test that after 3 failures, update() calls _refresh_data if reconnectAfter time is over."""
        self.service.failed_update_count = 3
        self.service.last_update_successful = False
        self.service._last_update = time.time() - 10 * 60  # more than reconnectAfter
        self.service._refresh_data.reset_mock()
        self.service.update()
        self.service._refresh_data.assert_called_once()

    def test_failed_update_count_reset_on_success(self):
        """Test that failed_update_count is reset to 0 after a successful update."""
        self.service.failed_update_count = 3
        self.service.last_update_successful = True
        self.service._last_update = time.time() - 10 * 60
        self.service._refresh_data = MagicMock()
        self.service.update()
        self.assertEqual(self.service.failed_update_count, 0)

    def test_reconnect_pause_not_applied_before_3_failures(self):
        """Test that reconnect pause is not applied if failed_update_count < 3 (should update as normal)."""
        self.service.failed_update_count = 2
        self.service.last_update_successful = False
        self.service._last_update = time.time()
        self.service._refresh_data.reset_mock()
        self.service.update()
        self.service._refresh_data.assert_called_once()

    def test_statuscode_set_on_reconnect_and_reset(self):
        """Test that on first reconnect error, StatusCode and values are set to error/zero, and on recovery StatusCode is set back to 7."""
        # Simulate error state
        self.service.failed_update_count = 3
        self.service._last_update = time.time()
        self.service.retryAfterSeconds = 60
        self.service.statuscode_set_on_reconnect = False
        self.service.update()
        self.assertEqual(self.service._dbusservice['/StatusCode'], 10)
        self.assertEqual(self.service._dbusservice['/Ac/Power'], 0)
        self.assertEqual(self.service._dbusservice['/Ac/L1/Current'], 0)
        self.assertEqual(self.service._dbusservice['/Ac/L1/Power'], 0)
        self.assertEqual(self.service._dbusservice['/Ac/L1/Voltage'], 0)
        self.assertTrue(self.service.statuscode_set_on_reconnect)

        # Simulate recovery
        self.service.failed_update_count = 0
        self.service.statuscode_set_on_reconnect = True
        self.service._refresh_data = MagicMock()
        self.service.is_data_up2date = MagicMock(return_value=True)
        self.service.dry_run = True
        self.service.set_dbus_values = MagicMock()
        self.service._update_index = MagicMock()
        self.service.last_update_successful = False
        self.service.update()
        self.assertEqual(self.service._dbusservice['/StatusCode'], 7)
        self.assertFalse(self.service.statuscode_set_on_reconnect)

    def test_timeout_mode_no_zero_before_timeout(self):
        """If ErrorMode=timeout and error_state_after_seconds=600, before 10min no zero/StatusCode=10 is sent."""
        self.service.error_mode = "timeout"
        self.service.error_state_after_seconds = 600  # 10 minutes
        self.service.last_update_successful = False
        self.service._last_update = time.time() - 300  # 5 minutes ago
        self.service.statuscode_set_on_reconnect = False
        self.service.set_dbus_values_to_zero = MagicMock()
        self.service.update()
        # Should NOT set zero values yet
        self.service.set_dbus_values_to_zero.assert_not_called()
        self.assertNotEqual(self.service._dbusservice['/StatusCode'], 10)

    def test_timeout_mode_zero_after_timeout(self):
        """If ErrorMode=timeout and error_state_after_seconds=600, after 10min zero/StatusCode=10 is sent."""
        self.service.error_mode = "timeout"
        self.service.error_state_after_seconds = 600  # 10 minutes
        self.service.last_update_successful = False
        self.service._last_update = time.time() - 601  # just over 10 minutes ago
        self.service.statuscode_set_on_reconnect = False
        self.service._refresh_data = MagicMock(side_effect=Exception("Test exception for error handling"))
        self.service.set_dbus_values_to_zero = MagicMock(wraps=self.service.set_dbus_values_to_zero)
        self.service.update()
        # Should set zero values now
        self.service.set_dbus_values_to_zero.assert_called_once()
        self.assertEqual(self.service._dbusservice['/StatusCode'], 10)

    def test_timeout_mode_timer_resets_on_success(self):
        """If in timeout mode a successful update occurs in between, the timer is reset and no zero values are sent."""
        self.service.error_mode = "timeout"
        self.service.error_state_after_seconds = 600  # 10 Minuten
        self.service.last_update_successful = False
        self.service._last_update = time.time() - 601  # Über Timeout, würde Nullwerte senden
        self.service.statuscode_set_on_reconnect = False
        self.service._refresh_data.side_effect = requests.exceptions.RequestException("Test exception")
        self.service.update()
        # reset refresh_data to simulate a successful update
        self.service._refresh_data = MagicMock()
        self.service.update()
        self.assertNotEqual(self.service._dbusservice['/StatusCode'], 10)


if __name__ == '__main__':
    unittest.main()
