"""Test utilities for DoorOpener application."""
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock

# Test Configuration
TEST_CONFIG = {
    'pins': {
        'test_user': '1234',
        'admin': 'admin123'
    },
    'admin': {
        'admin_password': 'testpass'
    },
    'server': {
        'test_mode': 'true',
        'port': '5000'
    },
    'HomeAssistant': {
        'url': 'http://test-ha:8123',
        'token': 'test-token',
        'switch_entity': 'switch.test_door',
        'battery_entity': 'sensor.test_door_battery'
    }
}

class MockResponse:
    """Mock response for requests.get()."""
    def __init__(self, status_code=200, json_data=None, text=None):
        self.status_code = status_code
        self._json = json_data or {}
        self.text = text or json.dumps(json_data) if json_data else ''

    def json(self):
        return self._json

def setup_test_config(mock_config):
    """Setup mock configuration for testing."""
    mock_config.return_value = MagicMock()
    mock_config.return_value.has_section.return_value = True
    
    def config_get(section, key, **kwargs):
        section_data = TEST_CONFIG.get(section, {})
        if key in section_data:
            return section_data[key]
        return kwargs.get('fallback')
    
    mock_config.return_value.get.side_effect = config_get
    mock_config.return_value.items.return_value = TEST_CONFIG['pins'].items()
    
    def get_boolean(section, key, **kwargs):
        val = config_get(section, key, **kwargs)
        return str(val).lower() == 'true' if val is not None else False
    
    mock_config.return_value.getboolean.side_effect = get_boolean
    mock_config.return_value.getint.side_effect = lambda s, k, **kw: int(config_get(s, k, **kw) or 0)
