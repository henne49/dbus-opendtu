""" Unit tests for the dbus_opendtu.py module """

import unittest
from unittest.mock import patch, MagicMock, mock_open, ANY
import sys
import os
import configparser

# Add the parent directory of dbus_opendtu to the system path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Mocking the dbus and other dependencies before importing the module to test
sys.modules['dbus'] = MagicMock()
sys.modules['vedbus'] = MagicMock()
# Mock the gi.repository.GLib module
sys.modules['gi'] = MagicMock()
sys.modules['gi.repository'] = MagicMock()
sys.modules['gi.repository.GLib'] = MagicMock()
sys.modules['gi.repository.GLib.MainLoop'] = MagicMock()
sys.modules['dbus.mainloop.glib'] = MagicMock()


from dbus_opendtu import (  # pylint: disable=E0401,C0413
    get_DbusServices,
    getConfig,
    sign_of_life_all_services,
    update_all_services,
    main
)  # noqa


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
        mock_dbus_service.assert_called_once()  # called once to check if there are inverters

    @patch("dbus_opendtu.DbusService")
    def test_get_config_with_invalid_NumberOfInverter_and_Template_values(self, mock_dbus_service):
        """ Test get_DbusServices with invalid NumberOfInverter and NumberOfTemplate values """
        # Create a mock config with the required values
        config = {
            "DEFAULT": {
                "NumberOfInvertersToQuery": "invalid",
                "NumberOfTemplates": "invalid",
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
        mock_dbus_service.assert_called_once()  # called once to check if there are inverters

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

    def test_sign_of_life_all_services(self):
        """ Test sign_of_life_all_services with a list of mock services """
        # Create a list of mock services
        mock_service_1 = MagicMock()
        mock_service_2 = MagicMock()
        services = [mock_service_1, mock_service_2]

        # Call the function
        result = sign_of_life_all_services(services)

        # Verify that the sign_of_life method was called on each service
        mock_service_1.sign_of_life.assert_called_once()
        mock_service_2.sign_of_life.assert_called_once()

        # Verify the return value
        self.assertTrue(result)

    def test_sign_of_life_all_services_with_empty_list(self):
        """ Test sign_of_life_all_services with an empty list """
        services = []

        # Call the function
        result = sign_of_life_all_services(services)

        # Verify the return value
        self.assertTrue(result)

    def test_sign_of_life_all_services_with_no_sign_of_life_method(self):
        """ Test sign_of_life_all_services with services missing sign_of_life method """
        # Create a list of mock services, one without sign_of_life method
        mock_service_1 = MagicMock()
        mock_service_2 = MagicMock()
        del mock_service_2.sign_of_life
        services = [mock_service_1, mock_service_2]

        # Call the function and expect an AttributeError
        with self.assertRaises(AttributeError):
            sign_of_life_all_services(services)

    @patch('dbus_opendtu.gobject')
    def test_update_all_services(self, mock_gobject):
        """ Test update_all_services with valid services """
        # Mock the current time
        mock_gobject.get_real_time.return_value = 2000000

        # Create mock services
        mock_service_1 = MagicMock()
        mock_service_1.polling_interval = 1000
        mock_service_1.last_polling = 1000

        mock_service_2 = MagicMock()
        mock_service_2.polling_interval = 2000
        mock_service_2.last_polling = 1000

        services = [mock_service_1, mock_service_2]

        # Call the function
        result = update_all_services(services)

        # Verify that the update method was called on each service
        mock_service_1.update.assert_called_once()
        mock_service_2.update.assert_not_called()

        # Verify that the last_polling attribute was updated
        self.assertEqual(mock_service_1.last_polling, 2000)
        self.assertEqual(mock_service_2.last_polling, 1000)

        # Verify the return value
        self.assertTrue(result)

    @patch('dbus_opendtu.gobject')
    def test_update_all_services_with_no_update_needed(self, mock_gobject):
        """ Test update_all_services when no update is needed """
        # Mock the current time
        mock_gobject.get_real_time.return_value = 2000000

        # Create mock services
        mock_service_1 = MagicMock()
        mock_service_1.polling_interval = 1000
        mock_service_1.last_polling = 1999

        mock_service_2 = MagicMock()
        mock_service_2.polling_interval = 2000
        mock_service_2.last_polling = 1999

        services = [mock_service_1, mock_service_2]

        # Call the function
        result = update_all_services(services)

        # Verify that the update method was not called on any service
        mock_service_1.update.assert_not_called()
        mock_service_2.update.assert_not_called()

        # Verify the return value
        self.assertTrue(result)

    @patch('dbus_opendtu.gobject')
    def test_update_all_services_with_empty_list(self, mock_gobject):
        """ Test update_all_services with an empty list """
        services = []

        # Call the function
        result = update_all_services(services)

        # Verify the return value
        self.assertTrue(result)

    @patch('dbus_opendtu.gobject')
    def test_update_all_services_with_missing_attributes(self, mock_gobject):
        """ Test update_all_services with services missing required attributes """
        # Mock the current time
        mock_gobject.get_real_time.return_value = 2000000

        # Create mock services, one missing required attributes
        mock_service_1 = MagicMock()
        mock_service_1.polling_interval = 1000
        mock_service_1.last_polling = 1000

        mock_service_2 = MagicMock()
        del mock_service_2.polling_interval
        del mock_service_2.last_polling

        services = [mock_service_1, mock_service_2]

        # Call the function and expect an AttributeError
        with self.assertRaises(AttributeError):
            update_all_services(services)

    @patch('dbus_opendtu.getConfig')
    @patch('dbus_opendtu.get_config_value')
    @patch('dbus_opendtu.get_DbusServices')
    @patch('dbus_opendtu.sign_of_life_all_services')
    @patch('dbus_opendtu.update_all_services')
    @patch('dbus_opendtu.gobject')
    def test_main(
        self,
        mock_gobject,
        mock_update_all_services,
        mock_sign_of_life_all_services,
        mock_get_dbus_services,
        mock_get_config_value,
        mock_get_config,
    ):
        """ Test the main function """
        # Mock the configuration
        mock_config = MagicMock()
        mock_get_config.return_value = mock_config
        mock_get_config_value.return_value = 1

        # Mock the services
        mock_services = [MagicMock()]
        mock_get_dbus_services.return_value = mock_services

        # Mock the timeout_add method
        def timeout_add_mock(interval, callback, *args, **kwargs):
            callback(*args, **kwargs)
            return True

        mock_gobject.timeout_add.side_effect = timeout_add_mock

        # Call the main function
        main()

        # Assertions to verify the behavior
        mock_get_config.assert_called_once()
        mock_get_dbus_services.assert_called_once_with(mock_config)
        mock_update_all_services.assert_called_once_with(mock_services)
        mock_sign_of_life_all_services.assert_called_once_with(mock_services)
        mock_gobject.MainLoop.assert_called_once()

    @patch('dbus_opendtu.get_DbusServices')
    @patch('dbus_opendtu.gobject')
    @patch('dbus_opendtu.logging')
    def test_main_exception(
        self,
        mock_logging,
        mock_gobject,
        mock_get_dbus_services,  # pylint: disable=W0613
    ):
        """ Test the main function with exception """
        # Mock gobject.MainLoop to raise an exception
        mock_gobject.MainLoop.side_effect = Exception("Test exception")

        main()
        mock_logging.critical.assert_called_once_with("Error at %s", "main",  exc_info=ANY)


if __name__ == '__main__':
    unittest.main()
