""" Unit tests for the dbus_opendtu.py module """

import unittest
from unittest.mock import patch, MagicMock
import sys

# Mocking the dbus and other dependencies before importing the module to test
sys.modules['dbus'] = MagicMock()
sys.modules['vedbus'] = MagicMock()
sys.modules['gi.repository'] = MagicMock()
sys.modules['dbus.mainloop.glib'] = MagicMock()

from dbus_opendtu import get_DbusServices  # pylint: disable=E0401,C0413 # noqa: E402


class TestRegisterService(unittest.TestCase):
    """ Test cases for the register_service function """

    @patch('dbus_opendtu.DbusService')
    @patch('dbus_opendtu.get_config_value')
    def test_register_service(self, mock_get_config_value, mock_dbus_service):
        """ Test the register_service function """
        def get_config_value_side_effect(key, *args, **kwargs):
            if isinstance(key, dict):
                key = key.get('key', 'mock_value')
            return {
                'number_of_inverters': 2,
                'number_of_templates': 1,
                'DTU': 'openDTU'
            }.get(key, 'mock_value')

        mock_get_config_value.side_effect = get_config_value_side_effect
        mock_dbus_service_instance = mock_dbus_service.return_value
        mock_dbus_service_instance.get_number_of_inverters.return_value = 1

        get_DbusServices({'DEFAULT': {'DTU': 'opendtu'}})

        # Add assertions to verify the behavior
        mock_dbus_service.assert_called_once()

        # Additional assertions
        mock_dbus_service.assert_called_once_with(
            servicename="mock_value",
            actual_inverter=0,
        )


if __name__ == '__main__':
    unittest.main()
