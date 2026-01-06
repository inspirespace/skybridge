"""src/backend/auth.py module."""
from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from typing import Any, Optional

import jwt
import requests
from fastapi import HTTPException


@dataclass
class _JwksCache:
    jwks_uri: str | None = None
    keys: list[dict[str, Any]] = None
    expires_at: float = 0.0


_JWKS_CACHE = _JwksCache(keys=[])


def user_id_from_request(authorization: Optional[str], x_user_id: Optional[str]) -> str:
    """Handle user id from request."""
    mode = (_env("AUTH_MODE") or "header").lower()
    if mode == "header":
        if not x_user_id:
            raise HTTPException(status_code=401, detail="Missing X-User-Id header")
        return x_user_id
    if mode != "oidc":
        raise HTTPException(status_code=500, detail=f"Unsupported auth mode: {mode}")
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Missing Authorization bearer token")
    token = authorization.split(" ", 1)[1].strip()
    if not token:
        raise HTTPException(status_code=401, detail="Missing Authorization bearer token")
    payload = _verify_token(token)
    user_id = (
        payload.get("preferred_username")
        or payload.get("email")
        or payload.get("sub")
    )
    if not isinstance(user_id, str) or not user_id:
        raise HTTPException(status_code=401, detail="Invalid token subject")
    return user_id


def user_id_from_event(event: dict[str, Any]) -> str:
    """Handle user id from event."""
    headers = event.get("headers") or {}
    authorization = headers.get("Authorization") or headers.get("authorization")
    x_user_id = headers.get("X-User-Id") or headers.get("x-user-id")
    return user_id_from_request(authorization, x_user_id)


def _verify_token(token: str) -> dict[str, Any]:
    """Internal helper for verify token."""
    issuer = _env("AUTH_ISSUER_URL")
    if not issuer:
        raise HTTPException(status_code=500, detail="AUTH_ISSUER_URL not configured")

    audience = _env("AUTH_AUDIENCE")
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
        # Keycloak may still be booting; surface a retryable error instead of 500.
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
    if _JWKS_CACHE.jwks_uri:
        return _JWKS_CACHE.jwks_uri
    config_url = issuer.rstrip("/") + "/.well-known/openid-configuration"
    response = requests.get(config_url, timeout=10)
    response.raise_for_status()
    data = response.json()
    jwks_uri = data.get("jwks_uri")
    if not jwks_uri:
        raise HTTPException(status_code=500, detail="OIDC config missing jwks_uri")
    _JWKS_CACHE.jwks_uri = jwks_uri
    return jwks_uri


def _env(name: str) -> str | None:
    """Internal helper for env."""
    value = os.getenv(name)
    if value is None or value.strip() == "":
        return None
    return value.strip()
