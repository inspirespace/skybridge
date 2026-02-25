"""Environment helpers for project and region resolution."""
from __future__ import annotations

import json
import os
from typing import Any
from functools import lru_cache
from pathlib import Path

DEFAULT_FIREBASE_REGION = "europe-west1"


def _clean_env(name: str) -> str | None:
    value = os.getenv(name)
    if not value:
        return None
    cleaned = value.strip()
    return cleaned or None


@lru_cache(maxsize=1)
def _read_firebaserc() -> dict[str, Any] | None:
    file_path = _clean_env("FIREBASERC_FILE")
    if file_path:
        candidate = Path(file_path).expanduser()
    else:
        candidate = Path(__file__).resolve().parents[2] / ".firebaserc"
    if not candidate.exists():
        return None
    try:
        payload = json.loads(candidate.read_text(encoding="utf-8"))
    except Exception:
        return None
    if isinstance(payload, dict):
        return payload
    return None


def _firebaserc_string(*path: str) -> str | None:
    payload = _read_firebaserc()
    if not payload:
        return None
    current: Any = payload
    for part in path:
        if not isinstance(current, dict):
            return None
        current = current.get(part)
        if current is None:
            return None
    if not isinstance(current, str):
        return None
    cleaned = current.strip()
    return cleaned or None


@lru_cache(maxsize=1)
def resolve_project_id() -> str | None:
    """Resolve project id from env, .firebaserc, or runtime credentials."""
    project_id = _clean_env("FIREBASE_PROJECT_ID")
    if project_id:
        return project_id
    project_id = _firebaserc_string("projects", "default")
    if project_id:
        return project_id
    try:
        import google.auth

        _, project_id = google.auth.default()
        if project_id:
            return project_id
    except Exception:
        return None
    return None


@lru_cache(maxsize=1)
def resolve_region() -> str:
    """Resolve region from env, .firebaserc, or global default."""
    return (
        _clean_env("FIREBASE_REGION")
        or _firebaserc_string("config", "region")
        or DEFAULT_FIREBASE_REGION
    )
