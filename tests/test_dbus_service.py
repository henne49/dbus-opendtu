''' This file contains the unit tests for the DbusService class. '''

import unittest
from unittest.mock import patch
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
            "NumberOfInvertersToQuery": 0
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

    @ patch('dbus_service.DbusService._get_config', return_value=template_config)
    @ patch('dbus_service.dbus')
    @ patch('dbus_service.logging')
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


if __name__ == '__main__':
    unittest.main()
