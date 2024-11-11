import unittest
from unittest.mock import patch, MagicMock
import sys
import os

# Mocking the dbus and other dependencies before importing the module to test
sys.modules['dbus'] = MagicMock()
sys.modules['vedbus'] = MagicMock()
sys.modules['gi.repository'] = MagicMock()
sys.modules['dbus.mainloop.glib'] = MagicMock()

# Add the directory containing dbus_opendtu.py to the Python path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from dbus_opendtu import register_service

class TestRegisterService(unittest.TestCase):
    @patch('dbus_opendtu.config', {'DEFAULT': {'DTU': 'opendtu'}})
    @patch('dbus_opendtu.DbusService')
    @patch('dbus_opendtu.get_config_value')
    @patch('dbus_opendtu.constants')
    
    def test_register_service(self, mock_constants, mock_get_config_value, mock_dbus_service):
        def get_config_value_side_effect(key, *args, **kwargs):
            if isinstance(key, dict):
                key = key.get('key', 'mock_value')
            return {
                'number_of_inverters': 2,
                'number_of_templates': 1,
                'DTU': 'openDTU'
            }.get(key, 'mock_value')

        mock_get_config_value.side_effect = get_config_value_side_effect
        #mock_dbus_service.return_value = MagicMock()
        mock_dbus_service_instance = mock_dbus_service.return_value
        mock_dbus_service_instance.get_number_of_inverters.return_value = 1

        register_service()

        # Add assertions to verify the behavior
        mock_dbus_service.assert_called_once()

        # Additional assertions
        mock_dbus_service.assert_called_once_with(
            servicename="mock_value",
            paths=unittest.mock.ANY,
            actual_inverter=0,
        )

if __name__ == '__main__':
    unittest.main()