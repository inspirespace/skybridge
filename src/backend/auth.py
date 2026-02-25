"""src/backend/auth.py module."""
from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from functools import lru_cache
from typing import Any, Optional

import jwt
import requests
from fastapi import HTTPException

from .env import resolve_project_id


@dataclass
class _JwksCache:
    jwks_uri: str | None = None
    keys: list[dict[str, Any]] = None
    expires_at: float = 0.0


_JWKS_CACHE = _JwksCache(keys=[])


@dataclass
class _AppCheckJwksCache:
    keys: list[dict[str, Any]] = None
    expires_at: float = 0.0


_APP_CHECK_JWKS_CACHE = _AppCheckJwksCache(keys=[])
_APP_CHECK_JWKS_URI = "https://firebaseappcheck.googleapis.com/v1/jwks"


def user_id_from_request(authorization: Optional[str], x_user_id: Optional[str]) -> str:
    """Handle user id from request."""
    mode = (_env("AUTH_MODE") or "header").lower()
    if mode == "header":
        if not x_user_id:
            raise HTTPException(status_code=401, detail="Missing X-User-Id header")
        return x_user_id
    if mode not in {"oidc", "firebase"}:
        raise HTTPException(status_code=500, detail=f"Unsupported auth mode: {mode}")
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Missing Authorization bearer token")
    token = authorization.split(" ", 1)[1].strip()
    if not token:
        raise HTTPException(status_code=401, detail="Missing Authorization bearer token")
    payload = _verify_token(token, mode)
    if mode == "firebase":
        user_id = payload.get("user_id") or payload.get("sub") or payload.get("email")
    else:
        user_id = payload.get("preferred_username") or payload.get("email") or payload.get("sub")
    if not isinstance(user_id, str) or not user_id:
        raise HTTPException(status_code=401, detail="Invalid token subject")
    return user_id


def user_id_from_event(event: dict[str, Any]) -> str:
    """Handle user id from event."""
    _verify_app_check_from_event(event)
    headers = event.get("headers") or {}
    authorization = headers.get("Authorization") or headers.get("authorization")
    x_user_id = headers.get("X-User-Id") or headers.get("x-user-id")
    return user_id_from_request(authorization, x_user_id)


def _verify_token(token: str, mode: str | None = None) -> dict[str, Any]:
    """Internal helper for verify token."""
    resolved_mode = (mode or _env("AUTH_MODE") or "header").lower()
    if _should_trust_emulator_tokens():
        try:
            payload = jwt.decode(
                token,
                options={
                    "verify_signature": False,
                    "verify_aud": False,
                    "verify_iss": False,
                },
            )
        except jwt.PyJWTError as exc:
            raise HTTPException(status_code=401, detail=f"Invalid token: {exc}") from exc
        return payload

    issuer = _env("AUTH_ISSUER_URL")
    if resolved_mode == "firebase" and not issuer:
        issuer = _default_firebase_issuer()
    if not issuer:
        raise HTTPException(status_code=500, detail="AUTH_ISSUER_URL not configured")

    audience = _env("AUTH_AUDIENCE")
    if resolved_mode == "firebase" and not audience:
        audience = _default_firebase_audience()
    client_id = _env("AUTH_CLIENT_ID")
    key = _resolve_key(token, issuer)
    try:
        payload = jwt.decode(
            token,
            key=key,
            algorithms=["RS256"],
            audience=audience if audience else None,
            issuer=issuer,
            options={"verify_aud": bool(audience)},
        )
    except jwt.PyJWTError as exc:
        raise HTTPException(status_code=401, detail=f"Invalid token: {exc}") from exc
    if client_id:
        azp = payload.get("azp")
        aud = payload.get("aud")
        aud_matches = False
        if isinstance(aud, str):
            aud_matches = aud == client_id
        elif isinstance(aud, list):
            aud_matches = client_id in aud
        if azp and azp != client_id:
            raise HTTPException(status_code=401, detail="Token audience mismatch")
        if not azp and not aud_matches:
            raise HTTPException(status_code=401, detail="Token audience mismatch")
    return payload


def _resolve_key(token: str, issuer: str) -> Any:
    """Internal helper for resolve key."""
    header = jwt.get_unverified_header(token)
    kid = header.get("kid")
    if not kid:
        raise HTTPException(status_code=401, detail="Token missing key id")

    keys = _load_jwks(issuer)
    for entry in keys:
        if entry.get("kid") == kid:
            return jwt.algorithms.RSAAlgorithm.from_jwk(json.dumps(entry))
    # Force JWKS refresh once in case keys rotated.
    _JWKS_CACHE.jwks_uri = None
    _JWKS_CACHE.expires_at = 0
    keys = _load_jwks(issuer)
    for entry in keys:
        if entry.get("kid") == kid:
            return jwt.algorithms.RSAAlgorithm.from_jwk(json.dumps(entry))
    raise HTTPException(status_code=401, detail="Unknown token key id")


def _load_jwks(issuer: str) -> list[dict[str, Any]]:
    """Internal helper for load jwks."""
    now = time.time()
    if _JWKS_CACHE.jwks_uri and _JWKS_CACHE.expires_at > now:
        return _JWKS_CACHE.keys or []

    jwks_uri = _jwks_uri_for_issuer(issuer)
    try:
        response = requests.get(jwks_uri, timeout=10)
        response.raise_for_status()
        payload = response.json()
    except requests.RequestException as exc:
    # Auth provider may still be booting; surface a retryable error instead of 500.
        raise HTTPException(
            status_code=503,
            detail="Auth provider not ready, retry in a few seconds.",
            headers={"Retry-After": "5"},
        ) from exc
    keys = payload.get("keys") or []

    _JWKS_CACHE.jwks_uri = jwks_uri
    _JWKS_CACHE.keys = keys
    _JWKS_CACHE.expires_at = now + 600
    return keys


def _jwks_uri_for_issuer(issuer: str) -> str:
    """Internal helper for jwks uri for issuer."""
    override = _env("AUTH_JWKS_URL")
    if override:
        return override
    if issuer.startswith("https://securetoken.google.com/"):
        return "https://www.googleapis.com/service_accounts/v1/jwk/securetoken@system.gserviceaccount.com"
    if _JWKS_CACHE.jwks_uri:
        return _JWKS_CACHE.jwks_uri
    config_url = issuer.rstrip("/") + "/.well-known/openid-configuration"
    response = requests.get(config_url, timeout=10)
    response.raise_for_status()
    data = response.json()
    jwks_uri = data.get("jwks_uri")
    if not jwks_uri:
        raise HTTPException(status_code=500, detail="Auth config missing jwks_uri")
    _JWKS_CACHE.jwks_uri = jwks_uri
    return jwks_uri


def _env(name: str) -> str | None:
    """Internal helper for env."""
    value = os.getenv(name)
    if value is None or value.strip() == "":
        return None
    return value.strip()


def _default_firebase_issuer() -> str | None:
    project_id = resolve_project_id()
    if not project_id:
        return None
    return f"https://securetoken.google.com/{project_id}"


def _default_firebase_audience() -> str | None:
    return resolve_project_id()


def _should_trust_emulator_tokens() -> bool:
    """Only allow unsigned token parsing when explicitly enabled for local dev.

    SECURITY: This function controls whether JWT signature verification is bypassed.
    It will NEVER return True if BACKEND_PRODUCTION=true is set, regardless of
    other environment variables. This prevents accidental emulator trust in production.
    """
    # Hard block in production - this check cannot be bypassed
    if _bool_env("BACKEND_PRODUCTION", False):
        return False
    if not _bool_env("AUTH_EMULATOR_TRUST_TOKENS", False):
        return False
    host = _env("FIREBASE_AUTH_EMULATOR_HOST")
    if not host:
        return False
    hostname = host.split(":", 1)[0].strip().lower()
    return hostname in {"localhost", "127.0.0.1", "::1"}


def _bool_env(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _verify_app_check_from_event(event: dict[str, Any]) -> None:
    """Verify Firebase App Check token when enforcement is enabled."""
    if not _should_enforce_app_check():
        return
    if _should_trust_emulator_tokens():
        return

    headers = event.get("headers") or {}
    app_check_token = _header_value(headers, "x-firebase-appcheck")
    if not app_check_token:
        raise HTTPException(status_code=401, detail="Missing App Check token")
    _verify_app_check_token(app_check_token)


def _should_enforce_app_check() -> bool:
    mode = (_env("AUTH_MODE") or "header").lower()
    if mode != "firebase":
        return False
    return _bool_env("APP_CHECK_ENFORCE", False)


def _header_value(headers: dict[str, Any], name: str) -> str | None:
    for key, value in headers.items():
        if key.lower() != name.lower():
            continue
        if isinstance(value, str):
            token = value.strip()
            return token or None
    return None


def _verify_app_check_token(token: str) -> dict[str, Any]:
    project_number = _resolve_project_number()
    if not project_number:
        raise HTTPException(status_code=500, detail="APP_CHECK_ENFORCE requires FIREBASE_PROJECT_NUMBER")

    issuer = f"https://firebaseappcheck.googleapis.com/{project_number}"
    audience = f"projects/{project_number}"
    key = _resolve_app_check_key(token)
    try:
        payload = jwt.decode(
            token,
            key=key,
            algorithms=["RS256"],
            audience=audience,
            issuer=issuer,
        )
    except jwt.PyJWTError as exc:
        raise HTTPException(status_code=401, detail=f"Invalid App Check token: {exc}") from exc
    subject = payload.get("sub")
    if not isinstance(subject, str) or not subject.strip():
        raise HTTPException(status_code=401, detail="Invalid App Check token subject")
    return payload


def _resolve_app_check_key(token: str) -> Any:
    header = jwt.get_unverified_header(token)
    kid = header.get("kid")
    if not kid:
        raise HTTPException(status_code=401, detail="App Check token missing key id")

    keys = _load_app_check_jwks()
    for entry in keys:
        if entry.get("kid") == kid:
            return jwt.algorithms.RSAAlgorithm.from_jwk(json.dumps(entry))

    # Force one refresh in case keys rotated.
    _APP_CHECK_JWKS_CACHE.keys = []
    _APP_CHECK_JWKS_CACHE.expires_at = 0
    keys = _load_app_check_jwks()
    for entry in keys:
        if entry.get("kid") == kid:
            return jwt.algorithms.RSAAlgorithm.from_jwk(json.dumps(entry))
    raise HTTPException(status_code=401, detail="Unknown App Check token key id")


def _load_app_check_jwks() -> list[dict[str, Any]]:
    now = time.time()
    if _APP_CHECK_JWKS_CACHE.expires_at > now and _APP_CHECK_JWKS_CACHE.keys:
        return _APP_CHECK_JWKS_CACHE.keys

    try:
        response = requests.get(_APP_CHECK_JWKS_URI, timeout=10)
        response.raise_for_status()
        payload = response.json()
    except requests.RequestException as exc:
        raise HTTPException(
            status_code=503,
            detail="App Check provider not ready, retry in a few seconds.",
            headers={"Retry-After": "5"},
        ) from exc

    keys = payload.get("keys") or []
    _APP_CHECK_JWKS_CACHE.keys = keys
    _APP_CHECK_JWKS_CACHE.expires_at = now + 600
    return keys


@lru_cache(maxsize=1)
def _resolve_project_number() -> str | None:
    for env_name in ("FIREBASE_PROJECT_NUMBER", "GOOGLE_CLOUD_PROJECT_NUMBER", "GCP_PROJECT_NUMBER"):
        value = _env(env_name)
        if value:
            return value

    project_id = resolve_project_id()
    if not project_id:
        return None

    try:
        import google.auth
        from google.auth.transport.requests import Request as GoogleAuthRequest
    except Exception:
        return None

    try:
        credentials, _ = google.auth.default(
            scopes=["https://www.googleapis.com/auth/cloud-platform.read-only"]
        )
        if not credentials.valid:
            credentials.refresh(GoogleAuthRequest())
        token = getattr(credentials, "token", None)
        if not token:
            return None
        response = requests.get(
            f"https://cloudresourcemanager.googleapis.com/v1/projects/{project_id}",
            headers={"Authorization": f"Bearer {token}"},
            timeout=10,
        )
        response.raise_for_status()
        payload = response.json()
        project_number = payload.get("projectNumber")
        if project_number is None:
            return None
        resolved = str(project_number).strip()
        return resolved or None
    except Exception:
        return None
