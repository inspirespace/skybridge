"""Object storage for job artifacts (GCS)."""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Protocol

from .env import resolve_project_id, resolve_region


class ObjectStoreProtocol(Protocol):
    """Shared interface for object stores."""

    @property
    def bucket(self) -> str: ...

    def key_for(self, *parts: str) -> str: ...

    def put_json(self, key: str, payload: dict[str, Any]) -> None: ...

    def put_file(self, key: str, path: Path) -> None: ...

    def get_json(self, key: str) -> dict[str, Any] | None: ...

    def get_bytes(self, key: str) -> bytes | None: ...

    def list_prefix(self, prefix: str) -> list[str]: ...

    def delete_prefix(self, prefix: str) -> None: ...


class GcsObjectStore:
    """GCS-backed object storage for job artifacts."""

    def __init__(
        self,
        *,
        bucket: str,
        prefix: str,
        project_id: str | None,
        location: str | None,
        create_bucket: bool,
    ) -> None:
        from google.api_core.exceptions import NotFound
        from google.cloud import storage

        self._prefix = prefix.strip("/")
        self._client = storage.Client(project=project_id or None)
        self._bucket = self._client.bucket(bucket)
        resolved_location = location or resolve_region()
        if create_bucket and not os.getenv("STORAGE_EMULATOR_HOST"):
            try:
                self._client.get_bucket(bucket)
            except NotFound:
                self._client.create_bucket(
                    self._bucket,
                    location=resolved_location,
                )

    @property
    def bucket(self) -> str:
        return self._bucket.name

    def key_for(self, *parts: str) -> str:
        prefix = self._prefix
        joined = "/".join(part.strip("/") for part in parts if part and part.strip("/"))
        if prefix:
            return f"{prefix}/{joined}"
        return joined

    def put_json(self, key: str, payload: dict[str, Any]) -> None:
        body = json.dumps(payload, indent=2).encode("utf-8")
        blob = self._bucket.blob(key)
        blob.upload_from_string(body, content_type="application/json")

    def put_file(self, key: str, path: Path) -> None:
        blob = self._bucket.blob(key)
        blob.upload_from_filename(str(path))

    def get_json(self, key: str) -> dict[str, Any] | None:
        blob = self._bucket.blob(key)
        if not blob.exists():
            return None
        payload = blob.download_as_text()
        return json.loads(payload)

    def get_bytes(self, key: str) -> bytes | None:
        blob = self._bucket.blob(key)
        if not blob.exists():
            return None
        return blob.download_as_bytes()

    def list_prefix(self, prefix: str) -> list[str]:
        keys: list[str] = []
        for blob in self._client.list_blobs(self._bucket, prefix=prefix):
            name = blob.name
            keys.append(name[len(prefix) + 1 :] if name.startswith(f"{prefix}/") else name)
        return sorted(keys)

    def delete_prefix(self, prefix: str) -> None:
        blobs = list(self._client.list_blobs(self._bucket, prefix=prefix))
        if blobs:
            self._bucket.delete_blobs(blobs)


def build_object_store_from_env() -> ObjectStoreProtocol | None:
    """Build object store from env."""
    if not _bool_env("BACKEND_GCS_ENABLED", False):
        return None
    bucket = os.getenv("GCS_BUCKET") or "skybridge-artifacts"
    prefix = os.getenv("GCS_PREFIX") or "jobs"
    project_id = resolve_project_id()
    location = resolve_region()
    create_bucket = _bool_env("GCS_CREATE_BUCKET", False)
    return GcsObjectStore(
        bucket=bucket,
        prefix=prefix,
        project_id=project_id,
        location=location,
        create_bucket=create_bucket,
    )


def _bool_env(name: str, default: bool) -> bool:
    """Internal helper for bool env."""
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}
