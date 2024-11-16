""" Unit tests for the dbus_opendtu.py module """

import unittest
from unittest.mock import patch, MagicMock, mock_open
import sys
import os
import configparser

# Add the parent directory of dbus_opendtu to the system path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Mocking the dbus and other dependencies before importing the module to test
sys.modules['dbus'] = MagicMock()
sys.modules['vedbus'] = MagicMock()
sys.modules['gi.repository'] = MagicMock()
sys.modules['dbus.mainloop.glib'] = MagicMock()


from dbus_opendtu import get_DbusServices, getConfig  # pylint: disable=E0401,C0413 # noqa: E402


class TestDbusOpendtu(unittest.TestCase):
    """ Test cases for the dbus_opendtu module """

    @patch('dbus_opendtu.DbusService')
    def test_register_service(self, mock_dbus_service):
        """ Test the register_service function """
        config = {
            "DEFAULT": {
                "NumberOfInvertersToQuery": "1",
                "NumberOfTemplates": "0",
                "DTU": "openDTU"
            },
            "INVERTER0": {
                "Phase": "L1",
                "DeviceInstance": "34",
                "AcPosition": "1"
            },
        }

        mock_dbus_service_instance = mock_dbus_service.return_value
        mock_dbus_service_instance.get_number_of_inverters.return_value = 1

        get_DbusServices(config)

        # Add assertions to verify the behavior
        mock_dbus_service.assert_called_once()

        # Additional assertions
        mock_dbus_service.assert_called_once_with(
            servicename="com.victronenergy.pvinverter",
            actual_inverter=0,
        )

    @patch(
        "builtins.open",
        new_callable=mock_open,
        read_data=(
            "[DEFAULT]\n"
            "Logging=INFO\n"
            "NumberOfInvertersToQuery=1\n"
            "NumberOfTemplates=1\n"
            "DTU=some_dtu"
        )
    )
    @patch("os.path.realpath")
    def test_get_config(self, mock_realpath, mock_open):  # pylint: disable=W0613
        """ Test the get_config function """
        # Mock the realpath to return a fixed path
        mock_realpath.return_value = "../config.example"

        # Call the function
        config = getConfig()

        # Verify the return type
        self.assertIsInstance(config, configparser.ConfigParser)

        # Verify the content of the config
        self.assertEqual(config["DEFAULT"]["Logging"], "INFO")
        self.assertEqual(config["DEFAULT"]["NumberOfInvertersToQuery"], "1")
        self.assertEqual(config["DEFAULT"]["NumberOfTemplates"], "1")
        self.assertEqual(config["DEFAULT"]["DTU"], "some_dtu")

    @patch('dbus_opendtu.DbusService')
    @patch('dbus_opendtu.get_config_value')
    def test_get_dbus_services_with_inverters(self, mock_get_config_value, mock_dbus_service):
        """ Test get_DbusServices with inverters """
        mock_get_config_value.side_effect = lambda config, key, section, index, default: f"mock_value_{index}"
        mock_dbus_service_instance = mock_dbus_service.return_value
        mock_dbus_service_instance.get_number_of_inverters.return_value = 2

        config = {
            "DEFAULT": {
                "NumberOfInvertersToQuery": "2",
                "NumberOfTemplates": "0",
                "DTU": "openDTU"
            }
        }

        services = get_DbusServices(config)

        self.assertEqual(len(services), 2)
        mock_dbus_service.assert_any_call(servicename="mock_value_0", actual_inverter=0)
        mock_dbus_service.assert_any_call(servicename="mock_value_1", actual_inverter=1)

    @patch("dbus_opendtu.get_config_value")
    @patch("dbus_opendtu.DbusService")
    def test_get_dbus_services_with_templates(self, mock_dbus_service, mock_get_config_value):
        """ Test get_DbusServices with templates """
        # Mock the get_config_value function to return specific values
        def get_config_value_side_effect(config, key, section, index, default):
            if key == "NumberOfInvertersToQuery":
                return 2  # Return an integer for the number of inverters
            return f"mock_value_{index}"

        mock_get_config_value.side_effect = get_config_value_side_effect

        # Mock the DbusService instance
        mock_dbus_service_instance = mock_dbus_service.return_value  # pylint: disable=W0612

        # Create a mock config
        config = MagicMock()

        # Call the function
        services = get_DbusServices(config)

        # Add assertions to verify the behavior
        self.assertIsInstance(services, list)
        self.assertEqual(len(services), 2)

    @patch("dbus_opendtu.DbusService")
    def test_get_dbus_services_with_no_inverters_or_templates(self, mock_dbus_service):
        """ Test get_DbusServices with no inverters or templates """
        # Create a mock config with the required values
        config = {
            "DEFAULT": {
                "NumberOfInvertersToQuery": "0",
                "NumberOfTemplates": "0",
                "DTU": "openDTU"
            },
            "INVERTER0": {},  # Add the required key to avoid KeyError
            "TEMPLATE0": {}   # Add the required key to avoid KeyError
        }

        # Mock the get_number_of_inverters method to return 0
        mock_dbus_service_instance = mock_dbus_service.return_value
        mock_dbus_service_instance.get_number_of_inverters.return_value = 0

        services = get_DbusServices(config)

        self.assertEqual(len(services), 0)
        mock_dbus_service.assert_not_called()

    @patch('dbus_opendtu.DbusService')
    @patch('dbus_opendtu.get_config_value')
    def test_get_dbus_services_with_missing_dtu_key(self, mock_get_config_value, mock_dbus_service):
        """ Test get_DbusServices with missing DTU key """
        mock_get_config_value.side_effect = lambda config, key, section, index, default: f"mock_value_{index}"
        mock_dbus_service_instance = mock_dbus_service.return_value

        config = {
            "DEFAULT": {
                "NumberOfInvertersToQuery": "1",
                "NumberOfTemplates": "1"
            }
        }

        services = get_DbusServices(config)

        self.assertIsNone(services)
        mock_dbus_service.assert_not_called()

        if __name__ == '__main__':
            unittest.main()


if __name__ == '__main__':
    unittest.main()
