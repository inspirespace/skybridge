"""Tests for backend auth helpers."""
from __future__ import annotations

import time

import pytest
import requests
from fastapi import HTTPException

import src.backend.auth as auth


class DummyResponse:
    def __init__(self, payload, status_code=200):
        self._payload = payload
        self.status_code = status_code

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"{self.status_code}")

    def json(self):
        return self._payload


@pytest.fixture(autouse=True)
def reset_jwks_cache():
    auth._JWKS_CACHE.jwks_uri = None
    auth._JWKS_CACHE.keys = []
    auth._JWKS_CACHE.expires_at = 0.0
    auth._APP_CHECK_JWKS_CACHE.keys = []
    auth._APP_CHECK_JWKS_CACHE.expires_at = 0.0
    auth._resolve_project_number.cache_clear()
    yield
    auth._JWKS_CACHE.jwks_uri = None
    auth._JWKS_CACHE.keys = []
    auth._JWKS_CACHE.expires_at = 0.0
    auth._APP_CHECK_JWKS_CACHE.keys = []
    auth._APP_CHECK_JWKS_CACHE.expires_at = 0.0
    auth._resolve_project_number.cache_clear()


def test_user_id_from_request_header_requires_user() -> None:
    """Test header auth requires X-User-Id."""
    with pytest.raises(HTTPException) as exc:
        auth.user_id_from_request(None, None)
    assert exc.value.status_code == 401


def test_user_id_from_request_header_accepts_user() -> None:
    """Test header auth returns user id."""
    assert auth.user_id_from_request(None, "pilot") == "pilot"


def test_user_id_from_request_unsupported_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test unsupported auth mode returns 500."""
    monkeypatch.setenv("AUTH_MODE", "unknown")
    with pytest.raises(HTTPException) as exc:
        auth.user_id_from_request(None, "pilot")
    assert exc.value.status_code == 500


def test_user_id_from_request_oidc_missing_token(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test OIDC mode requires bearer token."""
    monkeypatch.setenv("AUTH_MODE", "oidc")
    with pytest.raises(HTTPException) as exc:
        auth.user_id_from_request(None, None)
    assert exc.value.status_code == 401


def test_user_id_from_request_oidc_valid_token(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test OIDC mode derives user id from token payload."""
    monkeypatch.setenv("AUTH_MODE", "oidc")
    monkeypatch.setattr(auth, "_verify_token", lambda token, mode: {"preferred_username": "pilot"})
    assert auth.user_id_from_request("Bearer abc", None) == "pilot"


def test_user_id_from_request_firebase_valid_token(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test firebase mode behaves like OIDC."""
    monkeypatch.setenv("AUTH_MODE", "firebase")
    monkeypatch.setattr(auth, "_verify_token", lambda token, mode: {"user_id": "firebase-uid"})
    assert auth.user_id_from_request("Bearer abc", None) == "firebase-uid"


def test_user_id_from_request_defaults_to_firebase_on_functions_runtime(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test deployed functions default to firebase auth when AUTH_MODE is unset."""
    monkeypatch.delenv("AUTH_MODE", raising=False)
    monkeypatch.setenv("K_SERVICE", "skybridge-api")
    monkeypatch.setattr(auth, "resolve_project_id", lambda: "demo-project")
    monkeypatch.setattr(auth, "_verify_token", lambda token, mode: {"user_id": "firebase-uid"})
    assert auth.user_id_from_request("Bearer abc", None) == "firebase-uid"


def test_emulator_trust_requires_flag(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FIREBASE_AUTH_EMULATOR_HOST", "localhost:9099")
    monkeypatch.setenv("AUTH_EMULATOR_TRUST_TOKENS", "false")
    assert auth._should_trust_emulator_tokens() is False


def test_emulator_trust_requires_localhost(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FIREBASE_AUTH_EMULATOR_HOST", "emulator.example:9099")
    monkeypatch.setenv("AUTH_EMULATOR_TRUST_TOKENS", "true")
    assert auth._should_trust_emulator_tokens() is False


def test_user_id_from_request_oidc_invalid_subject(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test OIDC mode rejects empty subjects."""
    monkeypatch.setenv("AUTH_MODE", "oidc")
    monkeypatch.setattr(auth, "_verify_token", lambda token, mode: {"preferred_username": ""})
    with pytest.raises(HTTPException) as exc:
        auth.user_id_from_request("Bearer abc", None)
    assert exc.value.status_code == 401


def test_user_id_from_event_reads_headers(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test header extraction from event payload."""
    monkeypatch.setenv("AUTH_MODE", "header")
    event = {"headers": {"X-User-Id": "event-user"}}
    assert auth.user_id_from_event(event) == "event-user"


def test_user_id_from_event_requires_app_check_header(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AUTH_MODE", "firebase")
    monkeypatch.setenv("APP_CHECK_ENFORCE", "true")
    monkeypatch.setattr(auth, "_verify_token", lambda token, mode: {"user_id": "firebase-uid"})
    with pytest.raises(HTTPException) as exc:
        auth.user_id_from_event({"headers": {"Authorization": "Bearer token"}})
    assert exc.value.status_code == 401
    assert "App Check" in str(exc.value.detail)


def test_user_id_from_event_accepts_valid_app_check(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AUTH_MODE", "firebase")
    monkeypatch.setenv("APP_CHECK_ENFORCE", "true")
    monkeypatch.setattr(auth, "_verify_app_check_token", lambda token: {"sub": "app-id"})
    monkeypatch.setattr(auth, "_verify_token", lambda token, mode: {"user_id": "firebase-uid"})
    event = {
        "headers": {
            "Authorization": "Bearer token",
            "X-Firebase-AppCheck": "app-check-token",
        }
    }
    assert auth.user_id_from_event(event) == "firebase-uid"


def test_env_helper_strips(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AUTH_MODE", "  header ")
    assert auth._env("AUTH_MODE") == "header"
    monkeypatch.setenv("AUTH_MODE", "  ")
    assert auth._env("AUTH_MODE") is None


def test_jwks_uri_override(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AUTH_JWKS_URL", "https://issuer/jwks")
    assert auth._jwks_uri_for_issuer("https://issuer") == "https://issuer/jwks"


def test_jwks_uri_firebase_default() -> None:
    assert auth._jwks_uri_for_issuer("https://securetoken.google.com/demo-project") == (
        "https://www.googleapis.com/service_accounts/v1/jwk/securetoken@system.gserviceaccount.com"
    )


def test_jwks_uri_from_config(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_get(url, timeout=10):
        assert url.endswith("/.well-known/openid-configuration")
        return DummyResponse({"jwks_uri": "https://issuer/jwks"})

    monkeypatch.setattr(auth.requests, "get", fake_get)
    assert auth._jwks_uri_for_issuer("https://issuer") == "https://issuer/jwks"


def test_jwks_uri_missing_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(auth.requests, "get", lambda *_args, **_kwargs: DummyResponse({}))
    with pytest.raises(HTTPException) as exc:
        auth._jwks_uri_for_issuer("https://issuer")
    assert exc.value.status_code == 500


def test_load_jwks_uses_cache(monkeypatch: pytest.MonkeyPatch) -> None:
    auth._JWKS_CACHE.jwks_uri = "https://issuer/jwks"
    auth._JWKS_CACHE.keys = [{"kid": "k1"}]
    auth._JWKS_CACHE.expires_at = time.time() + 600
    monkeypatch.setattr(auth.requests, "get", lambda *_args, **_kwargs: pytest.fail("unexpected"))
    assert auth._load_jwks("https://issuer") == [{"kid": "k1"}]


def test_load_jwks_handles_request_error(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_get(*_args, **_kwargs):
        raise requests.RequestException("boom")

    monkeypatch.setattr(auth, "_jwks_uri_for_issuer", lambda _issuer: "https://issuer/jwks")
    monkeypatch.setattr(auth.requests, "get", fake_get)
    with pytest.raises(HTTPException) as exc:
        auth._load_jwks("https://issuer")
    assert exc.value.status_code == 503
    assert exc.value.headers["Retry-After"] == "5"


def test_resolve_key_refreshes(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(auth.jwt, "get_unverified_header", lambda _token: {"kid": "k1"})
    monkeypatch.setattr(
        auth.jwt.algorithms.RSAAlgorithm,
        "from_jwk",
        lambda _value: "KEY",
    )
    keys = [[], [{"kid": "k1"}]]

    def fake_load(_issuer):
        return keys.pop(0) if keys else [{"kid": "k1"}]

    monkeypatch.setattr(auth, "_load_jwks", fake_load)
    assert auth._resolve_key("token", "https://issuer") == "KEY"


def test_verify_token_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("AUTH_ISSUER_URL", raising=False)
    with pytest.raises(HTTPException) as exc:
        auth._verify_token("token", "oidc")
    assert exc.value.status_code == 500

    monkeypatch.setenv("AUTH_ISSUER_URL", "https://issuer")
    monkeypatch.setattr(auth, "_resolve_key", lambda *_args: "KEY")
    monkeypatch.setattr(auth.jwt, "decode", lambda *_args, **_kwargs: (_ for _ in ()).throw(auth.jwt.PyJWTError("bad")))
    with pytest.raises(HTTPException) as exc:
        auth._verify_token("token", "oidc")
    assert exc.value.status_code == 401


def test_verify_token_client_id_mismatch(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AUTH_ISSUER_URL", "https://issuer")
    monkeypatch.setenv("AUTH_CLIENT_ID", "client-1")
    monkeypatch.setattr(auth, "_resolve_key", lambda *_args: "KEY")
    monkeypatch.setattr(auth.jwt, "decode", lambda *_args, **_kwargs: {"aud": ["other"]})
    with pytest.raises(HTTPException) as exc:
        auth._verify_token("token", "oidc")
    assert exc.value.status_code == 401

    monkeypatch.setattr(auth.jwt, "decode", lambda *_args, **_kwargs: {"azp": "other", "aud": ["client-1"]})
    with pytest.raises(HTTPException) as exc:
        auth._verify_token("token", "oidc")
    assert exc.value.status_code == 401


def test_resolve_project_number_prefers_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FIREBASE_PROJECT_NUMBER", "123456789")
    assert auth._resolve_project_number() == "123456789"
