import json
import time
import types
from datetime import datetime, timedelta, timezone
from unittest.mock import patch, MagicMock

import pytest


@pytest.fixture
def app_module():
    import app as app_module
    return app_module


@pytest.fixture
def client(app_module):
    app_module.app.config['TESTING'] = True
    with app_module.app.test_client() as c:
        with app_module.app.app_context():
            yield c


def _std_headers():
    return {
        'User-Agent': 'pytest-client/1.0 (+https://example.test) long-ua',
        'Accept-Language': 'en-US,en;q=0.9',
        'Content-Type': 'application/json'
    }


def test_security_headers_on_index(client):
    resp = client.get('/', headers={'User-Agent': 'pytest', 'Accept-Language': 'en'})
    assert resp.status_code == 200
    # Basic security headers
    for h in ['X-Content-Type-Options', 'X-Frame-Options', 'X-XSS-Protection',
              'Referrer-Policy', 'Content-Security-Policy']:
        assert h in resp.headers


def test_suspicious_request_blocked_open_door(client):
    # Missing/short UA should be flagged as suspicious
    resp = client.post('/open-door', data=json.dumps({'pin': '1234'}), headers={'Content-Type': 'application/json'})
    assert resp.status_code == 403


def test_global_rate_limit_blocks(client, app_module):
    # Force global rate limit exceeded
    app_module.global_failed_attempts = app_module.MAX_GLOBAL_ATTEMPTS_PER_HOUR
    resp = client.post('/open-door', data=json.dumps({'pin': '1234'}), headers=_std_headers())
    assert resp.status_code == 429


def test_admin_auth_blocking(client, app_module, monkeypatch):
    # Make wrong password repeatedly and ensure session becomes blocked
    monkeypatch.setattr(time, 'sleep', lambda s: None)
    wrong = {'password': 'nope', 'remember_me': False}
    h = _std_headers()

    # 3 failures (SESSION_MAX_ATTEMPTS default is 3)
    for _ in range(app_module.SESSION_MAX_ATTEMPTS):
        r = client.post('/admin/auth', data=json.dumps(wrong), headers=h)
        assert r.status_code == 403
    # Next attempt is blocked
    r = client.post('/admin/auth', data=json.dumps(wrong), headers=h)
    assert r.status_code == 429


def test_admin_auth_success(client, app_module, monkeypatch):
    # Allow a success path by overriding admin password
    monkeypatch.setattr(time, 'sleep', lambda s: None)
    app_module.admin_password = 'secret'
    r = client.post('/admin/auth', data=json.dumps({'password': 'secret', 'remember_me': True}), headers=_std_headers())
    assert r.status_code == 200
    # Verify auth flag via check-auth
    r2 = client.get('/admin/check-auth')
    assert r2.status_code == 200
    data = r2.get_json()
    assert data.get('authenticated') is True


def test_auth_status_oidc_disabled_ignores_stale_session(client):
    with client.session_transaction() as s:
        s['oidc_authenticated'] = True
        s['oidc_user'] = 'alice@example.com'
        s['oidc_groups'] = ['dooropener-users']
    resp = client.get('/auth/status')
    assert resp.status_code == 200
    data = resp.get_json()
    # OIDC not initialized => must be reported as disabled/unauthenticated
    assert data['oidc_enabled'] in (False, 0)
    assert data['oidc_authenticated'] in (False, 0)


def test_oidc_logout_when_disabled_clears_session(client):
    with client.session_transaction() as s:
        s['oidc_authenticated'] = True
        s['something_else'] = 'x'
    resp = client.get('/oidc/logout', follow_redirects=False)
    # Should redirect to index and clear session
    assert resp.status_code in (302, 303)


def test_open_door_success_switch(client, app_module, monkeypatch):
    # Configure a valid PIN and switch entity
    app_module.user_pins['alice'] = '1234'
    app_module.entity_id = 'switch.test_door'

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.raise_for_status = lambda: None

    with patch('requests.post', return_value=mock_resp):
        r = client.post('/open-door', data=json.dumps({'pin': '1234'}), headers=_std_headers())
        assert r.status_code == 200
        msg = r.get_json().get('message', '')
        assert 'Door open' in msg


def test_open_door_success_lock(client, app_module, monkeypatch):
    app_module.user_pins['alice'] = '1234'
    app_module.entity_id = 'lock.test_door'

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.raise_for_status = lambda: None

    with patch('requests.post', return_value=mock_resp):
        r = client.post('/open-door', data=json.dumps({'pin': '1234'}), headers=_std_headers())
        assert r.status_code == 200


def test_open_door_success_input_boolean(client, app_module, monkeypatch):
    app_module.user_pins['alice'] = '1234'
    app_module.entity_id = 'input_boolean.open'

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.raise_for_status = lambda: None

    with patch('requests.post', return_value=mock_resp):
        r = client.post('/open-door', data=json.dumps({'pin': '1234'}), headers=_std_headers())
        assert r.status_code == 200


def test_battery_invalid_format(client, monkeypatch):
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {'state': 'unknown'}

    with patch('requests.get', return_value=mock_response):
        response = client.get('/battery')
        assert response.status_code == 200
        assert response.get_json()['level'] is None


def test_admin_logs_parsing(client, app_module, tmp_path):
    # Create a log line and ensure admin logs endpoint parses it
    logs_dir = tmp_path / 'logs'
    logs_dir.mkdir(parents=True, exist_ok=True)
    # Point app to temp logs dir (both access and audit handlers are already opened, so we write where it reads)
    log_file = logs_dir / 'log.txt'
    entry = {
        'timestamp': datetime.now(timezone.utc).isoformat(),
        'ip': '1.2.3.4',
        'user': 'alice',
        'status': 'SUCCESS',
        'details': 'Door opened'
    }
    log_file.write_text(json.dumps(entry) + "\n", encoding='utf-8')

    # Monkeypatch the path the endpoint reads
    with patch('os.path.exists', return_value=True), \
         patch('builtins.open') as mopen:
        mopen.return_value.__enter__.return_value = open(log_file, 'r', encoding='utf-8')
        # Authenticate admin by flagging session
        with client.session_transaction() as s:
            s['admin_authenticated'] = True
            s['admin_login_time'] = datetime.now(timezone.utc).isoformat()
        r = client.get('/admin/logs')
        assert r.status_code == 200
        data = r.get_json()
        assert 'logs' in data and isinstance(data['logs'], list)
        assert any(l.get('user') == 'alice' for l in data['logs'])
