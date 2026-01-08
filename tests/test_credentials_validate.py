"""Tests for credential validation endpoint."""
from __future__ import annotations

from fastapi.testclient import TestClient

from src.backend import app as app_module


def test_validate_credentials_success(monkeypatch):
    """Valid credentials return ok true."""
    def _noop(_credentials):
        return None

    monkeypatch.setattr(app_module, "validate_credentials", _noop)
    client = TestClient(app_module.app)
    response = client.post(
        "/credentials/validate",
        headers={"X-User-Id": "pilot@skybridge.dev"},
        json={
            "credentials": {
                "cloudahoy_username": "pilot@example.com",
                "cloudahoy_password": "secret",
                "flysto_username": "pilot@example.com",
                "flysto_password": "secret",
            }
        },
    )
    assert response.status_code == 200
    assert response.json() == {"ok": True}


def test_validate_credentials_failure(monkeypatch):
    """Invalid credentials return 400 with detail."""
    def _fail(_credentials):
        raise RuntimeError("bad credentials")

    monkeypatch.setattr(app_module, "validate_credentials", _fail)
    client = TestClient(app_module.app)
    response = client.post(
        "/credentials/validate",
        headers={"X-User-Id": "pilot@skybridge.dev"},
        json={
            "credentials": {
                "cloudahoy_username": "pilot@example.com",
                "cloudahoy_password": "wrong",
                "flysto_username": "pilot@example.com",
                "flysto_password": "wrong",
            }
        },
    )
    assert response.status_code == 400
    assert response.json().get("detail") == "bad credentials"
