''' This file contains the unit tests for the DbusService class. '''

import time
import unittest
from unittest.mock import MagicMock, patch
import os
import json
import requests
from constants import MODE_TIMEOUT
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
    elif url == 'http://localhost/api/limit/status':
        json_file_path = os.path.join(os.path.dirname(__file__), '../docs/opendtu_limit_status.json')
        with open(json_file_path, 'r', encoding="UTF-8") as file:
            json_data = json.load(file)
        return MockResponse(json_data, 200)
    elif url.startswith('http://localhost/api/devinfo/status?inv='):
        json_file_path = os.path.join(os.path.dirname(__file__), '../docs/opendtu_devinfo_status.json')
        with open(json_file_path, 'r', encoding="UTF-8") as file:
            json_data = json.load(file)
        return MockResponse(json_data, 200)
    return MockResponse(None, 404)


def mocked_requests_post(url, data=None, **kwargs):  # pylint: disable=unused-argument
    """Mock `requests.post` for OpenDTU /api/limit/config."""
    class MockResponse:
        def __init__(self, json_data, status_code):
            self.json_data = json_data
            self.status_code = status_code

        def json(self):
            return self.json_data

        def raise_for_status(self):
            if self.status_code != 200:
                raise requests.exceptions.HTTPError(f"{self.status_code} Error")

    if url == 'http://localhost/api/limit/config':
        return MockResponse({"type": "success", "message": "Settings saved!"}, 200)
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
            "DEFAULT": {"DTU": "ahoy", "RetryAfterSeconds": "10"},
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
        self.service.retry_after_seconds = 300  # seconds
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
        self.service.retry_after_seconds = 60
        self.service.reset_statuscode_on_next_success = False
        self.service.update()
        self.assertEqual(self.service._dbusservice['/StatusCode'], 10)
        self.assertEqual(self.service._dbusservice['/Ac/Power'], 0)
        self.assertEqual(self.service._dbusservice['/Ac/L1/Current'], 0)
        self.assertEqual(self.service._dbusservice['/Ac/L1/Power'], 0)
        self.assertEqual(self.service._dbusservice['/Ac/L1/Voltage'], 0)
        self.assertTrue(self.service.reset_statuscode_on_next_success)

        # Simulate recovery
        self.service.failed_update_count = 0
        self.service.reset_statuscode_on_next_success = True
        self.service._refresh_data = MagicMock()
        self.service.is_data_up2date = MagicMock(return_value=True)
        self.service.dry_run = True
        self.service.set_dbus_values = MagicMock()
        self.service._update_index = MagicMock()
        self.service.last_update_successful = False
        self.service.update()
        self.assertEqual(self.service._dbusservice['/StatusCode'], 7)
        self.assertFalse(self.service.reset_statuscode_on_next_success)

    def test_timeout_mode_no_zero_before_timeout(self):
        """If ErrorMode=timeout and error_state_after_seconds=600, before 10min no zero/StatusCode=10 is sent."""
        self.service.error_mode = MODE_TIMEOUT
        self.service.error_state_after_seconds = 600  # 10 minutes
        self.service.last_update_successful = False
        self.service._last_update = time.time() - 300  # 5 minutes ago
        self.service.reset_statuscode_on_next_success = False
        self.service.set_dbus_values_to_zero = MagicMock()
        self.service.update()
        # Should NOT set zero values yet
        self.service.set_dbus_values_to_zero.assert_not_called()
        self.assertNotEqual(self.service._dbusservice['/StatusCode'], 10)

    def test_timeout_mode_zero_after_timeout(self):
        """If ErrorMode=timeout and error_state_after_seconds=600, after 10min zero/StatusCode=10 is sent."""
        self.service.error_mode = MODE_TIMEOUT
        self.service.error_state_after_seconds = 600  # 10 minutes
        self.service.last_update_successful = False
        self.service._last_update = time.time() - 601  # just over 10 minutes ago
        self.service.reset_statuscode_on_next_success = False
        self.service._refresh_data = MagicMock(side_effect=Exception("Test exception for error handling"))
        self.service.set_dbus_values_to_zero = MagicMock(wraps=self.service.set_dbus_values_to_zero)
        self.service.update()
        # Should set zero values now
        self.service.set_dbus_values_to_zero.assert_called_once()
        self.assertEqual(self.service._dbusservice['/StatusCode'], 10)

    def test_timeout_mode_timer_resets_on_success(self):
        """If in timeout mode a successful update occurs in between, the timer is reset and no zero values are sent."""
        self.service.error_mode = MODE_TIMEOUT
        self.service.error_state_after_seconds = 600  # 10 Minuten
        self.service.last_update_successful = False
        self.service._last_update = time.time() - 601  # Über Timeout, würde Nullwerte senden
        self.service.reset_statuscode_on_next_success = False
        self.service._refresh_data.side_effect = requests.exceptions.RequestException("Test exception")
        self.service.update()
        # reset refresh_data to simulate a successful update; inverter also reachable again
        self.service._refresh_data = MagicMock()
        self.service.is_data_up2date = MagicMock(return_value=True)
        self.service.update()
        self.assertNotEqual(self.service._dbusservice['/StatusCode'], 10)

    def test_normal_operation_successful_update(self):
        """Test that in normal operation, update calls all expected methods and resets error state."""
        self.service.failed_update_count = 0
        self.service.last_update_successful = True
        self.service._last_update = time.time()
        self.service.dry_run = False
        self.service.is_data_up2date = MagicMock(return_value=True)
        self.service.update()
        self.service._refresh_data.assert_called_once()
        self.service.set_dbus_values.assert_called_once()
        self.service._update_index.assert_called_once()
        self.assertEqual(self.service.failed_update_count, 0)
        self.assertTrue(self.service.last_update_successful)

    def test_normal_operation_successful_update_timeout_mode(self):
        """Test that in timeout mode, normal operation calls all expected methods and resets error state."""
        self.service.error_mode = MODE_TIMEOUT
        self.service.error_state_after_seconds = 600  # 10 minutes
        self.service.failed_update_count = 0
        self.service.last_update_successful = True
        self.service._last_update = time.time()
        self.service.dry_run = False
        self.service.is_data_up2date = MagicMock(return_value=True)
        self.service._refresh_data = MagicMock()
        self.service.set_dbus_values = MagicMock()
        self.service._update_index = MagicMock()
        self.service.update()
        self.service._refresh_data.assert_called_once()
        self.service.set_dbus_values.assert_called_once()
        self.service._update_index.assert_called_once()
        self.assertEqual(self.service.failed_update_count, 0)
        self.assertTrue(self.service.last_update_successful)

    def test_config_values_are_read_correctly(self):
        """Test that config values are read and mapped to class attributes correctly."""
        config = {
            "DEFAULT": {
                "DTU": "ahoy",
                "ErrorMode": "timeout",
                "RetryAfterSeconds": "123",
                "MinRetriesUntilFail": "7",
                "ErrorStateAfterSeconds": "456"
            },
            "INVERTER0": {
                "Phase": "L1",
                "DeviceInstance": "34",
                "AcPosition": "1",
                "Host": "localhost",
            },
        }
        with patch('dbus_service.DbusService._get_config', return_value=config):
            service = DbusService("com.victronenergy.pvinverter", 0)
            self.assertEqual(service.error_mode, "timeout")
            self.assertEqual(service.retry_after_seconds, 123)
            self.assertEqual(service.min_retries_until_fail, 7)
            self.assertEqual(service.error_state_after_seconds, 456)


class PowerLimitTest(unittest.TestCase):
    """Tests for OpenDTU power-limit integration."""

    def setUp(self):
        DbusService._meter_data = None

    def tearDown(self):
        DbusService._meter_data = None

    opendtu_config = {
        "DEFAULT": {
            "DTU": "opendtu",
            "Username": "admin",
            "Password": "secret",
        },
        "INVERTER0": {
            "Phase": "L1",
            "DeviceInstance": "34",
            "AcPosition": "1",
            "Host": "localhost",
        },
    }

    def _make_service(self):
        service = DbusService("com.victronenergy.pvinverter", 0)
        # _dbusservice is a MagicMock by default; swap for a real dict for path I/O
        service._dbusservice = {
            "/Ac/MaxPower": None,
            "/Ac/PowerLimit": None,
            "/StatusCode": 7,
        }
        service.serial = "114182940773"
        return service

    @patch('dbus_service.DbusService._get_config', return_value=opendtu_config)
    @patch('dbus_service.dbus')
    @patch('dbus_service.logging')
    @patch('dbus_service.requests.get', side_effect=mocked_requests_get)
    def test_init_seeds_max_power_and_power_limit_from_opendtu(
            self, mock_get, mock_logging, mock_dbus, mock_config):
        """At init, /Ac/MaxPower and /Ac/PowerLimit are seeded via add_path(initial=...)
           from /api/limit/status, so no post-register writes emit PropertiesChanged."""
        DbusService._meter_data = None
        service = DbusService("com.victronenergy.pvinverter", 0)
        by_path = {c.args[0]: c.args[1] for c in service._dbusservice.add_path.call_args_list}
        self.assertEqual(by_path["/Ac/MaxPower"], 2000)
        # limit_relative=50 and max_power=2000 -> 1000W initial PowerLimit
        self.assertEqual(by_path["/Ac/PowerLimit"], 1000.0)

    @patch('dbus_service.DbusService._get_config', return_value=opendtu_config)
    @patch('dbus_service.dbus')
    @patch('dbus_service.logging')
    @patch('dbus_service.requests.get', side_effect=mocked_requests_get)
    def test_refresh_limit_status_skips_seed_when_already_seeded(
            self, mock_get, mock_logging, mock_dbus, mock_config):
        """Once init (or a prior fallback) has seeded the paths, _refresh_limit_status
           must not re-write them — that would round-trip via onchangecallback and POST."""
        DbusService._meter_data = None
        service = self._make_service()
        service._limit_seeded = True
        service._refresh_limit_status()
        self.assertIsNone(service._dbusservice["/Ac/MaxPower"])
        self.assertIsNone(service._dbusservice["/Ac/PowerLimit"])
        # limit_set_status=Ok -> RUNNING (7)
        self.assertEqual(service._dbusservice["/StatusCode"], 7)

    @patch('dbus_service.DbusService._get_config', return_value=opendtu_config)
    @patch('dbus_service.dbus')
    @patch('dbus_service.logging')
    @patch('dbus_service.requests.get', side_effect=mocked_requests_get)
    def test_refresh_limit_status_fallback_seeds_when_init_failed(
            self, mock_get, mock_logging, mock_dbus, mock_config):
        """If init's fetch failed, the first successful _refresh_limit_status seeds
           /Ac/MaxPower and /Ac/PowerLimit and flips _limit_seeded so it fires once."""
        DbusService._meter_data = None
        service = self._make_service()
        service._limit_seeded = False
        service._refresh_limit_status()
        self.assertEqual(service._dbusservice["/Ac/MaxPower"], 2000)
        # limit_relative=50, max_power=2000 -> 1000W
        self.assertEqual(service._dbusservice["/Ac/PowerLimit"], 1000.0)
        self.assertTrue(service._limit_seeded)

    @patch('dbus_service.DbusService._get_config', return_value=opendtu_config)
    @patch('dbus_service.dbus')
    @patch('dbus_service.logging')
    def test_refresh_limit_status_maps_error_status(
            self, mock_logging, mock_dbus, mock_config):
        """Non-Ok limit_set_status maps to STATUSCODE_ERROR on /StatusCode."""
        failing_payload = {
            "114182940773": {"limit_relative": 50, "max_power": 2000, "limit_set_status": "Failure"}
        }

        def failing_get(url, **_kwargs):
            if url.endswith("/livedata/status"):
                return mocked_requests_get(url)
            if url.endswith("/limit/status"):
                class R:
                    status_code = 200
                    def json(self):
                        return failing_payload
                    def raise_for_status(self):
                        pass
                return R()
            return mocked_requests_get(url)

        DbusService._meter_data = None
        with patch('dbus_service.requests.get', side_effect=failing_get):
            service = self._make_service()
            service._refresh_limit_status()
        self.assertEqual(service._dbusservice["/StatusCode"], 10)

    @patch('dbus_service.DbusService._get_config', return_value=opendtu_config)
    @patch('dbus_service.dbus')
    @patch('dbus_service.logging')
    @patch('dbus_service.requests.get', side_effect=mocked_requests_get)
    @patch('dbus_service.requests.post', side_effect=mocked_requests_post)
    def test_apply_power_limit_posts_and_accepts(
            self, mock_post, mock_get, mock_logging, mock_dbus, mock_config):
        """Writing /Ac/PowerLimit POSTs the correct payload and the change is accepted."""
        DbusService._meter_data = None
        service = self._make_service()
        # _refresh_limit_status needs a populated MaxPower for clamp logic; set directly
        service._dbusservice["/Ac/MaxPower"] = 2000
        accepted = service._handlechangedvalue("/Ac/PowerLimit", 300)
        self.assertTrue(accepted)
        self.assertEqual(mock_post.call_count, 1)
        call_url = mock_post.call_args.kwargs.get("url") or mock_post.call_args.args[0]
        self.assertEqual(call_url, "http://localhost/api/limit/config")
        form = mock_post.call_args.kwargs["data"]
        self.assertEqual(json.loads(form["data"]),
                         {"serial": "114182940773", "limit_type": 0, "limit_value": 300})

    @patch('dbus_service.DbusService._get_config', return_value=opendtu_config)
    @patch('dbus_service.dbus')
    @patch('dbus_service.logging')
    @patch('dbus_service.requests.get', side_effect=mocked_requests_get)
    @patch('dbus_service.requests.post', side_effect=requests.exceptions.ConnectionError("boom"))
    def test_apply_power_limit_rejects_on_post_failure(
            self, mock_post, mock_get, mock_logging, mock_dbus, mock_config):
        """A failing POST causes _handlechangedvalue to return False (DBus write rejected)."""
        DbusService._meter_data = None
        service = self._make_service()
        service._dbusservice["/Ac/MaxPower"] = 2000
        accepted = service._handlechangedvalue("/Ac/PowerLimit", 500)
        self.assertFalse(accepted)

    @patch('dbus_service.DbusService._get_config', return_value=opendtu_config)
    @patch('dbus_service.dbus')
    @patch('dbus_service.logging')
    @patch('dbus_service.requests.get', side_effect=mocked_requests_get)
    def test_fetch_opendtu_devinfo_builds_url_and_returns_json(
            self, mock_get, mock_logging, mock_dbus, mock_config):
        """fetch_opendtu_devinfo calls /api/devinfo/status?inv=<serial> and returns parsed JSON."""
        DbusService._meter_data = None
        service = self._make_service()
        data = service.fetch_opendtu_devinfo("114182940773")
        self.assertEqual(data["hw_model_name"], "HMS-2000-4T")
        self.assertEqual(data["fw_build_version"], 10027)
        called_urls = [c.kwargs.get("url") or (c.args[0] if c.args else None)
                       for c in mock_get.call_args_list]
        self.assertIn("http://localhost/api/devinfo/status?inv=114182940773", called_urls)

    def test_decode_version_int_and_string(self):
        """Int versions split into 2-digit groups; strings pass through."""
        self.assertEqual(DbusService._decode_version(10027), "1.0.27")
        self.assertEqual(DbusService._decode_version(101), "0.1.1")
        self.assertEqual(DbusService._decode_version("01.10"), "01.10")
        self.assertIsNone(DbusService._decode_version(None))

    @patch('dbus_service.DbusService._get_config', return_value=opendtu_config)
    @patch('dbus_service.dbus')
    @patch('dbus_service.logging')
    @patch('dbus_service.requests.get', side_effect=mocked_requests_get)
    def test_init_uses_devinfo_for_management_paths(
            self, mock_get, mock_logging, mock_dbus, mock_config):
        """At init, /ProductName, /FirmwareVersion, /HardwareVersion come from devinfo."""
        DbusService._meter_data = None
        service = DbusService("com.victronenergy.pvinverter", 0)
        by_path = {c.args[0]: c.args[1] for c in service._dbusservice.add_path.call_args_list}
        self.assertEqual(by_path["/ProductName"], "HMS-2000-4T")
        self.assertEqual(by_path["/FirmwareVersion"], "1.0.27 (2023-06-05 10:24:00)")
        self.assertEqual(by_path["/HardwareVersion"], "01.10")

    @patch('dbus_service.DbusService._get_config', return_value=opendtu_config)
    @patch('dbus_service.dbus')
    @patch('dbus_service.logging')
    def test_init_valid_data_false_sets_status_error(
            self, mock_logging, mock_dbus, mock_config):
        """valid_data=false in devinfo makes initial /StatusCode = ERROR."""
        from constants import STATUSCODE_ERROR

        def routed_get(url, **_kw):
            if url.startswith("http://localhost/api/devinfo/status"):
                class R:
                    status_code = 200
                    def json(self):
                        return {"valid_data": False, "hw_model_name": "HMS-2000-4T",
                                "hw_version": "01.10", "fw_build_version": 10027,
                                "fw_build_datetime": "2023-06-05 10:24:00"}
                    def raise_for_status(self):
                        pass
                return R()
            return mocked_requests_get(url)

        DbusService._meter_data = None
        with patch('dbus_service.requests.get', side_effect=routed_get):
            service = DbusService("com.victronenergy.pvinverter", 0)
        by_path = {c.args[0]: c.args[1] for c in service._dbusservice.add_path.call_args_list}
        self.assertEqual(by_path["/StatusCode"], STATUSCODE_ERROR)


class PvInverterSchemaTest(unittest.TestCase):
    """PVINVERTER_PATHS/VICTRON_PATHS separation and /Position + /PositionIsAdjustable."""

    def test_pvinverter_paths_exclude_inverter_only(self):
        from constants import PVINVERTER_PATHS, VICTRON_PATHS
        self.assertNotIn("/Ac/Out/L1/I", PVINVERTER_PATHS)
        self.assertNotIn("/Dc/0/Voltage", PVINVERTER_PATHS)
        # VICTRON_PATHS is the superset used by the inverter service
        self.assertIn("/Ac/Out/L1/I", VICTRON_PATHS)
        self.assertIn("/Dc/0/Voltage", VICTRON_PATHS)
        # Shared pvinverter paths appear in both
        self.assertIn("/Ac/MaxPower", PVINVERTER_PATHS)
        self.assertIn("/Ac/PowerLimit", PVINVERTER_PATHS)

    opendtu_config = {
        "DEFAULT": {"DTU": "opendtu"},
        "INVERTER0": {
            "Phase": "L1", "DeviceInstance": "34", "AcPosition": "1", "Host": "localhost",
        },
    }

    def setUp(self):
        DbusService._meter_data = None

    def tearDown(self):
        DbusService._meter_data = None

    @patch('dbus_service.DbusService._get_config', return_value=opendtu_config)
    @patch('dbus_service.dbus')
    @patch('dbus_service.logging')
    @patch('dbus_service.requests.get', side_effect=mocked_requests_get)
    def test_pvinverter_registers_position_paths(
            self, mock_get, mock_logging, mock_dbus, mock_config):
        """Pvinverter service registers /Position and /PositionIsAdjustable=1."""
        service = DbusService("com.victronenergy.pvinverter", 0)
        registered_paths = [call.args[0] for call in service._dbusservice.add_path.call_args_list]
        self.assertIn("/Position", registered_paths)
        self.assertIn("/PositionIsAdjustable", registered_paths)
        # /PositionIsAdjustable is registered with initial=1
        position_adj_call = next(c for c in service._dbusservice.add_path.call_args_list
                                 if c.args[0] == "/PositionIsAdjustable")
        self.assertEqual(position_adj_call.args[1], 1)

    @patch('dbus_service.DbusService._get_config', return_value=opendtu_config)
    @patch('dbus_service.dbus')
    @patch('dbus_service.logging')
    @patch('dbus_service.requests.get', side_effect=mocked_requests_get)
    def test_init_status_code_is_startup(
            self, mock_get, mock_logging, mock_dbus, mock_config):
        """Initial /StatusCode is STARTUP(0), not RUNNING(7)."""
        from constants import STATUSCODE_STARTUP
        service = DbusService("com.victronenergy.pvinverter", 0)
        status_calls = [c for c in service._dbusservice.add_path.call_args_list
                        if c.args[0] == "/StatusCode"]
        self.assertEqual(status_calls[0].args[1], STATUSCODE_STARTUP)


class OfflinePublishingTest(unittest.TestCase):
    """Regression: at night (OpenDTU reachable=false) yield totals and StatusCode=ERROR
    must still be written to DBus, not skipped."""

    def setUp(self):
        DbusService._meter_data = None

    def tearDown(self):
        DbusService._meter_data = None

    def test_set_dbus_values_publishes_yield_and_error_when_offline(self):
        from constants import STATUSCODE_ERROR
        service = DbusService(servicename="testing", actual_inverter=0)
        service.dtuvariant = "opendtu"
        service._servicename = "com.victronenergy.pvinverter"
        service.pvinverterphase = "L1"
        service.useyieldday = False
        service.dry_run = False
        # Craft OpenDTU livedata with an unreachable, non-producing inverter that
        # nevertheless still has a YieldTotal accumulated from earlier in the day.
        service.set_test_data({
            "inverters": [{
                "serial": "114182000001",
                "reachable": False,
                "producing": False,
                "AC": {"0": {"Power": {"v": 0}, "Voltage": {"v": 0}, "Current": {"v": 0},
                             "YieldTotal": {"v": 12.345}}},
                "DC": {"0": {"Voltage": {"v": 0}}},
            }],
        })
        service._dbusservice = {p: None for p in [
            "/Ac/Power", "/Ac/L1/Voltage", "/Ac/L1/Current", "/Ac/L1/Power",
            "/Ac/L1/Energy/Forward", "/Ac/Energy/Forward", "/StatusCode",
        ]}
        service.set_dbus_values()
        self.assertEqual(service._dbusservice["/Ac/Energy/Forward"], 12.345)
        self.assertEqual(service._dbusservice["/Ac/L1/Energy/Forward"], 12.345)
        self.assertEqual(service._dbusservice["/Ac/Power"], 0)
        self.assertEqual(service._dbusservice["/StatusCode"], STATUSCODE_ERROR)


class ComputeStatusCodeTest(unittest.TestCase):
    """Tests for _compute_status_code mapping reachable/producing onto StatusCode."""

    def setUp(self):
        DbusService._meter_data = None

    def tearDown(self):
        DbusService._meter_data = None

    def _make(self, dtuvariant):
        service = DbusService(servicename="testing", actual_inverter=0)
        service.dtuvariant = dtuvariant
        return service

    def test_opendtu_reachable_and_producing_is_running(self):
        from constants import STATUSCODE_RUNNING
        service = self._make("opendtu")
        service.set_test_data({"inverters": [{"reachable": True, "producing": True}]})
        self.assertEqual(service._compute_status_code(), STATUSCODE_RUNNING)

    def test_opendtu_reachable_not_producing_is_standby(self):
        from constants import STATUSCODE_STANDBY
        service = self._make("opendtu")
        service.set_test_data({"inverters": [{"reachable": True, "producing": False}]})
        self.assertEqual(service._compute_status_code(), STATUSCODE_STANDBY)

    def test_opendtu_unreachable_is_standby(self):
        from constants import STATUSCODE_STANDBY
        service = self._make("opendtu")
        service.set_test_data({"inverters": [{"reachable": False, "producing": False}]})
        self.assertEqual(service._compute_status_code(), STATUSCODE_STANDBY)


if __name__ == '__main__':
    unittest.main()
