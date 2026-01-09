"""tests/test_backend_web.py module."""
from __future__ import annotations

import json

from src.backend.web import landing_page


def _extract_auth_config(html: str) -> dict:
    marker = "const authConfig = "
    start = html.index(marker) + len(marker)
    end = html.index(";", start)
    return json.loads(html[start:end].strip())


def test_landing_page_defaults(monkeypatch):
    monkeypatch.delenv("AUTH_MODE", raising=False)
    monkeypatch.delenv("AUTH_BROWSER_ISSUER_URL", raising=False)
    monkeypatch.delenv("AUTH_ISSUER_URL", raising=False)
    monkeypatch.delenv("AUTH_CLIENT_ID", raising=False)
    monkeypatch.delenv("AUTH_SCOPE", raising=False)
    monkeypatch.delenv("AUTH_REDIRECT_PATH", raising=False)
    monkeypatch.delenv("AUTH_TOKEN_PROXY", raising=False)
    monkeypatch.delenv("DEV_PREFILL_CREDENTIALS", raising=False)
    monkeypatch.delenv("CLOUD_AHOY_EMAIL", raising=False)
    monkeypatch.delenv("CLOUD_AHOY_PASSWORD", raising=False)
    monkeypatch.delenv("FLYSTO_EMAIL", raising=False)
    monkeypatch.delenv("FLYSTO_PASSWORD", raising=False)

    response = landing_page()
    html = response.body.decode("utf-8")
    config = _extract_auth_config(html)

    assert config["enabled"] is False
    assert config["issuer"] == ""
    assert config["clientId"] == "skybridge-dev"
    assert config["scope"] == "openid profile email"
    assert config["redirectPath"] == "/auth/callback"
    assert config["tokenProxy"] is False
    assert config["prefillEnabled"] is False
    assert config["prefill"] == {}


def test_landing_page_oidc_prefill(monkeypatch):
    monkeypatch.setenv("AUTH_MODE", "oidc")
    monkeypatch.setenv("AUTH_BROWSER_ISSUER_URL", "https://issuer.example.com")
    monkeypatch.setenv("AUTH_CLIENT_ID", "client-123")
    monkeypatch.setenv("AUTH_SCOPE", "openid")
    monkeypatch.setenv("AUTH_REDIRECT_PATH", "/callback")
    monkeypatch.setenv("AUTH_TOKEN_PROXY", "true")
    monkeypatch.setenv("DEV_PREFILL_CREDENTIALS", "1")
    monkeypatch.setenv("CLOUD_AHOY_EMAIL", "pilot@example.com")
    monkeypatch.setenv("CLOUD_AHOY_PASSWORD", "secret")
    monkeypatch.setenv("FLYSTO_EMAIL", "flysto@example.com")
    monkeypatch.setenv("FLYSTO_PASSWORD", "pass")

    response = landing_page()
    html = response.body.decode("utf-8")
    config = _extract_auth_config(html)

    assert config["enabled"] is True
    assert config["issuer"] == "https://issuer.example.com"
    assert config["clientId"] == "client-123"
    assert config["scope"] == "openid"
    assert config["redirectPath"] == "/callback"
    assert config["tokenProxy"] is True
    assert config["prefillEnabled"] is True
    assert config["prefill"]["cloudahoy_username"] == "pilot@example.com"
    assert config["prefill"]["flysto_username"] == "flysto@example.com"


def test_landing_page_oidc_default_issuer(monkeypatch):
    monkeypatch.setenv("AUTH_MODE", "oidc")
    monkeypatch.delenv("AUTH_BROWSER_ISSUER_URL", raising=False)
    monkeypatch.delenv("AUTH_ISSUER_URL", raising=False)

    response = landing_page()
    html = response.body.decode("utf-8")
    config = _extract_auth_config(html)

    assert config["enabled"] is True
    assert config["issuer"].endswith("/realms/skybridge-dev")
