from unittest.mock import MagicMock


def _std_headers():
    return {
        "User-Agent": "pytest-client/1.0 (+https://example.test) long-ua",
        "Accept-Language": "en-US,en;q=0.9",
        "Content-Type": "application/json",
    }


def test_verify_defaults_to_true_without_ca_bundle(client, monkeypatch):
    # Arrange: no ca_bundle configured; app should use verify=True
    import app as app_module

    # Ensure no custom bundle
    monkeypatch.setattr(app_module, "ha_ca_bundle", "")

    captured = {}

    def fake_get(url, headers=None, timeout=None, verify=None):
        captured["verify"] = verify
        resp = MagicMock()
        resp.status_code = 200
        resp.json.return_value = {"state": "95"}
        return resp

    monkeypatch.setattr("requests.get", fake_get)

    # Act
    r = client.get("/battery")

    # Assert
    assert r.status_code == 200
    assert captured.get("verify") is True


def test_verify_uses_ca_bundle_when_set(client, monkeypatch):
    # Arrange: set a custom CA bundle path
    import app as app_module

    ca_path = "/etc/dooropener/ha-ca.pem"
    monkeypatch.setattr(app_module, "ha_ca_bundle", ca_path)

    captured = {}

    def fake_get(url, headers=None, timeout=None, verify=None):
        captured["verify"] = verify
        resp = MagicMock()
        resp.status_code = 200
        resp.json.return_value = {"state": "88"}
        return resp

    monkeypatch.setattr("requests.get", fake_get)

    # Act
    r = client.get("/battery")

    # Assert
    assert r.status_code == 200
    assert captured.get("verify") == ca_path


def test_post_verify_defaults_to_true_without_ca_bundle(client, monkeypatch):
    # Arrange
    import app as app_module

    app_module.test_mode = False
    app_module.user_pins["alice"] = "1234"
    monkeypatch.setattr(app_module, "ha_ca_bundle", "")

    captured = {}

    def fake_post(url, headers=None, json=None, timeout=None, verify=None):
        captured["verify"] = verify
        resp = MagicMock()
        resp.status_code = 200
        resp.raise_for_status = lambda: None
        return resp

    monkeypatch.setattr("requests.post", fake_post)

    # Act
    r = client.post("/open-door", json={"pin": "1234"}, headers=_std_headers())

    # Assert
    assert r.status_code == 200
    assert captured.get("verify") is True


def test_post_verify_uses_ca_bundle_when_set(client, monkeypatch):
    # Arrange
    import app as app_module

    app_module.test_mode = False
    app_module.user_pins["bob"] = "5678"
    ca_path = "/etc/dooropener/ha-ca.pem"
    monkeypatch.setattr(app_module, "ha_ca_bundle", ca_path)

    captured = {}

    def fake_post(url, headers=None, json=None, timeout=None, verify=None):
        captured["verify"] = verify
        resp = MagicMock()
        resp.status_code = 200
        resp.raise_for_status = lambda: None
        return resp

    monkeypatch.setattr("requests.post", fake_post)

    # Act
    r = client.post("/open-door", json={"pin": "5678"}, headers=_std_headers())

    # Assert
    assert r.status_code == 200
    assert captured.get("verify") == ca_path
