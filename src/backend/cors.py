"""CORS origin helpers."""
from __future__ import annotations

import os
import re
from urllib.parse import urlparse

from .env import resolve_project_id 

_LOOPBACK_ORIGIN_REGEX = r"^https?://(localhost|127\.0\.0\.1|\[::1\])(?::\d+)?$"


def _split_origins(raw: str | None) -> list[str]:
    if not raw:
        return []
    return [value.strip() for value in raw.split(",") if value.strip()]


def _normalize_domain(raw_domain: str) -> str | None:
    cleaned = raw_domain.strip()
    if not cleaned:
        return None
    candidate = cleaned if "://" in cleaned else f"https://{cleaned}"
    try:
        parsed = urlparse(candidate)
    except Exception:
        return None
    hostname = (parsed.hostname or "").strip().lower().rstrip(".")
    if not hostname:
        return None
    return hostname


def resolve_cors_origins() -> tuple[list[str], str | None]:
    """Resolve allowed origins and an optional regex for dynamic matches."""
    explicit = _split_origins(os.getenv("CORS_ALLOW_ORIGINS"))
    if explicit:
        return explicit, None

    dev_domain = _normalize_domain(os.getenv("SKYBRIDGE_DEV_DOMAIN") or "")
    if dev_domain:
        return [
            f"https://{dev_domain}",
            f"https://emulator.{dev_domain}",
            f"http://{dev_domain}",
            f"http://emulator.{dev_domain}",
        ], None

    project_id = resolve_project_id()
    if project_id:
        return [
            f"https://{project_id}.web.app",
            f"https://{project_id}.firebaseapp.com",
        ], None

    return ["http://localhost"], _LOOPBACK_ORIGIN_REGEX


def origin_is_allowed(origin: str, allowed_origins: list[str], allowed_origin_regex: str | None) -> bool:
    if not origin:
        return False
    if "*" in allowed_origins:
        return True
    if origin in allowed_origins:
        return True
    if allowed_origin_regex and re.match(allowed_origin_regex, origin):
        return True
    return False


def select_allow_origin(request_origin: str, allowed_origins: list[str], allowed_origin_regex: str | None) -> str:
    """Choose the Access-Control-Allow-Origin value."""
    if "*" in allowed_origins:
        return "*"
    if origin_is_allowed(request_origin, allowed_origins, allowed_origin_regex):
        return request_origin
    return allowed_origins[0]

