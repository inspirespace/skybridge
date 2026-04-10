"""Tests for backend auth helpers."""
from __future__ import annotations

import time

import pytest
import requests
from fastapi import HTTPException

import src.backend.auth as auth


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


def test_user_id_from_request_requires_bearer_token() -> None:
    with pytest.raises(HTTPException) as exc:
        auth.user_id_from_request(None)
    assert exc.value.status_code == 401


def test_user_id_from_request_accepts_verified_subject(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(auth, "_verify_token", lambda _token: {"user_id": "firebase-uid"})
    assert auth.user_id_from_request("Bearer abc") == "firebase-uid"


def test_user_id_from_request_rejects_empty_subject(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(auth, "_verify_token", lambda _token: {"user_id": ""})
    with pytest.raises(HTTPException) as exc:
        auth.user_id_from_request("Bearer abc")
    assert exc.value.status_code == 401


def test_emulator_trust_requires_flag(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FIREBASE_AUTH_EMULATOR_HOST", "localhost:9099")
    monkeypatch.setenv("AUTH_EMULATOR_TRUST_TOKENS", "false")
    assert auth._should_trust_emulator_tokens() is False


def test_emulator_trust_requires_localhost(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FIREBASE_AUTH_EMULATOR_HOST", "emulator.example:9099")
    monkeypatch.setenv("AUTH_EMULATOR_TRUST_TOKENS", "true")
    assert auth._should_trust_emulator_tokens() is False


def test_user_id_from_event_reads_authorization_header(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(auth, "_verify_token", lambda _token: {"sub": "event-user"})
    event = {"headers": {"Authorization": "Bearer token"}}
    assert auth.user_id_from_event(event) == "event-user"


def test_user_id_from_event_requires_app_check_header(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_CHECK_ENFORCE", "true")
    monkeypatch.setattr(auth, "_verify_token", lambda _token: {"user_id": "firebase-uid"})
    with pytest.raises(HTTPException) as exc:
        auth.user_id_from_event({"headers": {"Authorization": "Bearer token"}})
    assert exc.value.status_code == 401
    assert "App Check" in str(exc.value.detail)


def test_user_id_from_event_accepts_valid_app_check(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_CHECK_ENFORCE", "true")
    monkeypatch.setattr(auth, "_verify_app_check_token", lambda _token: {"sub": "app-id"})
    monkeypatch.setattr(auth, "_verify_token", lambda _token: {"user_id": "firebase-uid"})
    event = {
        "headers": {
            "Authorization": "Bearer token",
            "X-Firebase-AppCheck": "app-check-token",
        }
    }
    assert auth.user_id_from_event(event) == "firebase-uid"


def test_env_helper_strips(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FIREBASE_PROJECT_NUMBER", " 123456789 ")
    assert auth._env("FIREBASE_PROJECT_NUMBER") == "123456789"
    monkeypatch.setenv("FIREBASE_PROJECT_NUMBER", "  ")
    assert auth._env("FIREBASE_PROJECT_NUMBER") is None


def test_load_jwks_uses_cache(monkeypatch: pytest.MonkeyPatch) -> None:
    auth._JWKS_CACHE.jwks_uri = auth._FIREBASE_JWKS_URI
    auth._JWKS_CACHE.keys = [{"kid": "k1"}]
    auth._JWKS_CACHE.expires_at = time.time() + 600
    monkeypatch.setattr(auth.requests, "get", lambda *_args, **_kwargs: pytest.fail("unexpected"))
    assert auth._load_jwks() == [{"kid": "k1"}]


def test_load_jwks_handles_request_error(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_get(*_args, **_kwargs):
        raise requests.RequestException("boom")

    monkeypatch.setattr(auth.requests, "get", fake_get)
    with pytest.raises(HTTPException) as exc:
        auth._load_jwks()
    assert exc.value.status_code == 503
    assert exc.value.headers["Retry-After"] == "5"


def test_resolve_key_refreshes(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(auth.jwt, "get_unverified_header", lambda _token: {"kid": "k1"})
    monkeypatch.setattr(auth.jwt.algorithms.RSAAlgorithm, "from_jwk", lambda _value: "KEY")
    keys = [[], [{"kid": "k1"}]]

    def fake_load():
        return keys.pop(0) if keys else [{"kid": "k1"}]

    monkeypatch.setattr(auth, "_load_jwks", fake_load)
    assert auth._resolve_key("token") == "KEY"


def test_verify_token_requires_project_id(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(auth, "resolve_project_id", lambda: None)
    with pytest.raises(HTTPException) as exc:
        auth._verify_token("token")
    assert exc.value.status_code == 500


def test_verify_token_jwt_decode_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(auth, "resolve_project_id", lambda: "demo-project")
    monkeypatch.setattr(auth, "_resolve_key", lambda *_args: "KEY")
    monkeypatch.setattr(
        auth.jwt,
        "decode",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(auth.jwt.PyJWTError("bad")),
    )
    with pytest.raises(HTTPException) as exc:
        auth._verify_token("token")
    assert exc.value.status_code == 401


def test_resolve_project_number_prefers_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FIREBASE_PROJECT_NUMBER", "123456789")
    assert auth._resolve_project_number() == "123456789"
