import pytest
from flask import session


def make_client():
    from app import app as flask_app
    flask_app.config['TESTING'] = True
    return flask_app.test_client()


def test_auth_status_defaults(client=None):
    client = client or make_client()
    resp = client.get('/auth/status')
    assert resp.status_code == 200
    data = resp.get_json()
    # OIDC disabled by default in example tests
    assert 'oidc_enabled' in data
    assert data['oidc_authenticated'] in (False, True)


def test_auth_status_with_session():
    client = make_client()
    with client.session_transaction() as s:
        s['oidc_authenticated'] = True
        s['oidc_user'] = 'alice@example.com'
        s['oidc_groups'] = ['dooropener-users']
    resp = client.get('/auth/status')
    assert resp.status_code == 200
    data = resp.get_json()
    assert data['oidc_authenticated'] is True
    assert data['user'] == 'alice@example.com'
    assert 'dooropener-users' in data.get('groups', [])


def test_open_door_pinless_oidc_allowed(monkeypatch):
    import app as app_module
    # Ensure policy allows pinless open and test mode avoids HA calls
    app_module.require_pin_for_oidc = False
    app_module.oidc_user_group = 'dooropener-users'
    app_module.test_mode = True

    client = make_client()
    with client.session_transaction() as s:
        s['oidc_authenticated'] = True
        s['oidc_user'] = 'alice'
        s['oidc_groups'] = ['dooropener-users']

    resp = client.post('/open-door', json={})
    assert resp.status_code == 200
    data = resp.get_json()
    assert data['status'] == 'success'
    assert 'Welcome home' in data['message']


def test_open_door_pinless_blocked_when_require_pin(monkeypatch):
    import app as app_module
    app_module.require_pin_for_oidc = True
    app_module.oidc_user_group = ''  # any user allowed, but PIN still required
    app_module.test_mode = True

    client = make_client()
    with client.session_transaction() as s:
        s['oidc_authenticated'] = True
        s['oidc_user'] = 'bob'
        s['oidc_groups'] = ['dooropener-users']

    resp = client.post('/open-door', json={})
    # No PIN provided -> should be a 400 requiring PIN
    assert resp.status_code == 400
    data = resp.get_json()
    assert data['status'] == 'error'
    assert 'PIN' in data['message']


def test_open_door_pinless_blocked_when_group_not_allowed(monkeypatch):
    import app as app_module
    app_module.require_pin_for_oidc = False
    app_module.oidc_user_group = 'dooropener-users'  # require specific group
    app_module.test_mode = True

    client = make_client()
    with client.session_transaction() as s:
        s['oidc_authenticated'] = True
        s['oidc_user'] = 'charlie'
        s['oidc_groups'] = ['some-other-group']

    resp = client.post('/open-door', json={})
    # Not in allowed group -> PIN required path triggers 400 when missing
    assert resp.status_code == 400
    data = resp.get_json()
    assert data['status'] == 'error'
    assert 'PIN' in data['message']
