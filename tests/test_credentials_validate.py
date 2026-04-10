"""Tests for credential validation endpoint."""
from __future__ import annotations

import json

from src.backend import lambda_handlers


def _make_event(payload: dict) -> dict:
    return {
        "headers": {"Authorization": "Bearer token"},
        "body": json.dumps(payload),
        "rawPath": "/credentials/validate",
        "requestContext": {"http": {"method": "POST", "path": "/credentials/validate"}},
    }


def test_validate_credentials_success(monkeypatch):
    """Valid credentials return ok true."""
    monkeypatch.setattr(lambda_handlers, "user_id_from_event", lambda _event: "pilot@skybridge.dev")

    def _noop(_credentials):
        return None

    monkeypatch.setattr(lambda_handlers, "validate_credentials", _noop)
    response = lambda_handlers.validate_credentials_handler(
        _make_event(
            {
                "credentials": {
                    "cloudahoy_username": "pilot@example.com",
                    "cloudahoy_password": "secret",
                    "flysto_username": "pilot@example.com",
                    "flysto_password": "secret",
                }
            }
        ),
        None,
    )
    assert response["statusCode"] == 200
    assert json.loads(response["body"]) == {"ok": True}


def test_validate_credentials_failure(monkeypatch):
    """Invalid credentials return 400 with detail."""
    monkeypatch.setattr(lambda_handlers, "user_id_from_event", lambda _event: "pilot@skybridge.dev")

    def _fail(_credentials):
        raise RuntimeError("bad credentials")

    monkeypatch.setattr(lambda_handlers, "validate_credentials", _fail)
    response = lambda_handlers.validate_credentials_handler(
        _make_event(
            {
                "credentials": {
                    "cloudahoy_username": "pilot@example.com",
                    "cloudahoy_password": "wrong",
                    "flysto_username": "pilot@example.com",
                    "flysto_password": "wrong",
                }
            }
        ),
        None,
    )
    assert response["statusCode"] == 400
    assert json.loads(response["body"]).get("detail") == "bad credentials"
