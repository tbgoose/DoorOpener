import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import pytest
from app import app as flask_app

@pytest.fixture
def client():
    flask_app.config['TESTING'] = True
    with flask_app.test_client() as client:
        yield client

def test_index(client):
    response = client.get('/')
    assert response.status_code == 200
    assert b'Door' in response.data or b'door' in response.data

def test_battery(client, monkeypatch):
    # Mock requests.get to simulate Home Assistant response
    import requests
    class MockResponse:
        def __init__(self, status_code, json_data):
            self.status_code = status_code
            self._json = json_data
        def json(self):
            return self._json
    def mock_get(*args, **kwargs):
        return MockResponse(200, {'state': '85'})
    monkeypatch.setattr(requests, 'get', mock_get)
    response = client.get('/battery')
    assert response.status_code == 200
    assert response.json['level'] == 85

def test_open_door_missing_pin(client):
    response = client.post('/open-door', json={})
    assert response.status_code == 400
    assert response.json['status'] == 'error'

def test_open_door_invalid_pin(client):
    response = client.post('/open-door', json={'pin': 'abc'})
    assert response.status_code == 400
    assert response.json['status'] == 'error'

def test_admin_logs_unauthenticated(client):
    response = client.get('/admin/logs')
    assert response.status_code == 401
    assert 'error' in response.json

#this test was AI generated lmao
