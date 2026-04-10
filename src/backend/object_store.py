"""Object storage for job artifacts (GCS)."""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Protocol

from .env import resolve_project_id, resolve_storage_bucket


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
    ) -> None:
        from google.cloud import storage

        self._prefix = prefix.strip("/")
        self._client = storage.Client(project=project_id or None)
        self._bucket = self._client.bucket(bucket)

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


def build_object_store_from_env() -> ObjectStoreProtocol:
    """Build object store from env."""
    bucket = resolve_storage_bucket()
    if not bucket:
        raise RuntimeError(
            "Firebase Storage bucket could not be resolved. Set GCS_BUCKET, provide FIREBASE_CONFIG storageBucket, or configure FIREBASE_PROJECT_ID."
        )
    prefix = os.getenv("GCS_PREFIX") or "jobs"
    project_id = resolve_project_id()
    return GcsObjectStore(
        bucket=bucket,
        prefix=prefix,
        project_id=project_id,
    )
