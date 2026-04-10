"""Environment helpers for project, region, and storage resolution."""
from __future__ import annotations

import json
import os
from functools import lru_cache
from pathlib import Path
from typing import Any

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
def _read_firebase_config() -> dict[str, Any] | None:
    raw = _clean_env("FIREBASE_CONFIG")
    if not raw:
        return None
    try:
        if raw.lstrip().startswith("{"):
            payload = json.loads(raw)
        else:
            payload = json.loads(Path(raw).expanduser().read_text(encoding="utf-8"))
    except Exception:
        return None
    if isinstance(payload, dict):
        return payload
    return None


def _firebase_config_string(*path: str) -> str | None:
    payload = _read_firebase_config()
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


def _pick_storage_bucket_candidate(project_id: str, bucket_names: list[str]) -> str | None:
    """Choose the most likely Firebase/GCS bucket for this project."""
    if not bucket_names:
        return None

    normalized = [name.strip() for name in bucket_names if isinstance(name, str) and name.strip()]
    normalized = [
        name
        for name in normalized
        if not (
            name.startswith("gcf-v2-sources-")
            or name.startswith("gcf-v2-uploads-")
            or name.startswith("gcf-sources-")
        )
    ]
    if not normalized:
        return None

    preferred = (
        f"{project_id}.firebasestorage.app",
        f"{project_id}.appspot.com",
    )
    for candidate in preferred:
        if candidate in normalized:
            return candidate

    project_prefixed = [name for name in normalized if name.startswith(f"{project_id}.")]
    if len(project_prefixed) == 1:
        return project_prefixed[0]

    firebase_like = [
        name
        for name in normalized
        if name.endswith(".firebasestorage.app") or name.endswith(".appspot.com")
    ]
    if len(firebase_like) == 1:
        return firebase_like[0]

    if len(normalized) == 1:
        return normalized[0]
    return None


@lru_cache(maxsize=4)
def _discover_project_storage_bucket(project_id: str) -> str | None:
    """Discover an existing project bucket before falling back to guessed names."""
    if not project_id:
        return None
    try:
        from google.cloud import storage

        client = storage.Client(project=project_id or None)
        bucket_names = [bucket.name for bucket in client.list_buckets(project=project_id)]
    except Exception:
        return None
    return _pick_storage_bucket_candidate(project_id, bucket_names)


@lru_cache(maxsize=1)
def resolve_storage_bucket() -> str | None:
    """Resolve Firebase Storage bucket from env, runtime config, discovery, or project default."""
    explicit_bucket = _clean_env("GCS_BUCKET") or _clean_env("FIREBASE_STORAGE_BUCKET")
    if explicit_bucket:
        return explicit_bucket

    firebase_bucket = _firebase_config_string("storageBucket")
    if firebase_bucket:
        return firebase_bucket

    project_id = resolve_project_id()
    if not project_id:
        return None

    discovered_bucket = _discover_project_storage_bucket(project_id)
    if discovered_bucket:
        return discovered_bucket

    return f"{project_id}.firebasestorage.app"


@lru_cache(maxsize=1)
def resolve_region() -> str:
    """Resolve region from env, .firebaserc, or global default."""
    return (
        _clean_env("FIREBASE_REGION")
        or _firebaserc_string("config", "region")
        or DEFAULT_FIREBASE_REGION
    )
