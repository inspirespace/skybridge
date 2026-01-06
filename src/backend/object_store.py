"""S3-backed object storage for job artifacts."""
from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError


@dataclass(frozen=True)
class ObjectStoreConfig:
    bucket: str
    prefix: str
    endpoint_url: str | None
    region: str | None
    access_key: str | None
    secret_key: str | None
    use_ssl: bool
    verify_ssl: bool
    sse: bool


class ObjectStore:
    def __init__(self, config: ObjectStoreConfig) -> None:
        """Internal helper for init  ."""
        self._config = config
        client_config = Config(signature_version="s3v4", s3={"addressing_style": "path"})
        self._client = boto3.client(
            "s3",
            endpoint_url=config.endpoint_url or None,
            region_name=config.region or None,
            aws_access_key_id=config.access_key or None,
            aws_secret_access_key=config.secret_key or None,
            use_ssl=config.use_ssl,
            verify=config.verify_ssl,
            config=client_config,
        )
        self._ensure_bucket()

    @property
    def bucket(self) -> str:
        """Handle bucket."""
        return self._config.bucket

    def key_for(self, *parts: str) -> str:
        """Handle key for."""
        prefix = self._config.prefix.strip("/")
        joined = "/".join(part.strip("/") for part in parts if part and part.strip("/"))
        if prefix:
            return f"{prefix}/{joined}"
        return joined

    def put_json(self, key: str, payload: dict[str, Any]) -> None:
        """Handle put json."""
        body = json.dumps(payload, indent=2).encode("utf-8")
        extra = {"ContentType": "application/json"}
        if self._config.sse:
            extra["ServerSideEncryption"] = "AES256"
        self._client.put_object(Bucket=self.bucket, Key=key, Body=body, **extra)

    def put_file(self, key: str, path: Path) -> None:
        """Handle put file."""
        extra: dict[str, Any] = {}
        if self._config.sse:
            extra["ServerSideEncryption"] = "AES256"
        self._client.upload_file(str(path), self.bucket, key, ExtraArgs=extra or None)

    def get_json(self, key: str) -> dict[str, Any] | None:
        """Get json."""
        try:
            response = self._client.get_object(Bucket=self.bucket, Key=key)
        except ClientError:
            return None
        body = response.get("Body")
        if not body:
            return None
        payload = body.read().decode("utf-8")
        return json.loads(payload)

    def get_bytes(self, key: str) -> bytes | None:
        """Get bytes."""
        try:
            response = self._client.get_object(Bucket=self.bucket, Key=key)
        except ClientError:
            return None
        body = response.get("Body")
        if not body:
            return None
        return body.read()

    def list_prefix(self, prefix: str) -> list[str]:
        """Handle list prefix."""
        keys: list[str] = []
        paginator = self._client.get_paginator("list_objects_v2")
        for page in paginator.paginate(Bucket=self.bucket, Prefix=prefix):
            contents = page.get("Contents") or []
            for item in contents:
                key = item.get("Key")
                if not key:
                    continue
                keys.append(key[len(prefix) + 1 :] if key.startswith(f"{prefix}/") else key)
        return sorted(keys)

    def delete_prefix(self, prefix: str) -> None:
        """Delete prefix."""
        paginator = self._client.get_paginator("list_objects_v2")
        for page in paginator.paginate(Bucket=self.bucket, Prefix=prefix):
            contents = page.get("Contents") or []
            keys = [{"Key": item["Key"]} for item in contents if item.get("Key")]
            if not keys:
                continue
            self._client.delete_objects(Bucket=self.bucket, Delete={"Objects": keys})

    def _ensure_bucket(self) -> None:
        """Internal helper for ensure bucket."""
        try:
            self._client.head_bucket(Bucket=self.bucket)
            return
        except ClientError:
            pass
        params: dict[str, Any] = {"Bucket": self.bucket}
        if self._config.region and self._config.region != "us-east-1":
            params["CreateBucketConfiguration"] = {"LocationConstraint": self._config.region}
        self._client.create_bucket(**params)


def build_object_store_from_env() -> ObjectStore | None:
    """Build object store from env."""
    if not _bool_env("BACKEND_S3_ENABLED", False):
        return None
    bucket = os.getenv("S3_BUCKET") or "skybridge-artifacts"
    prefix = os.getenv("S3_PREFIX") or "jobs"
    endpoint_url = os.getenv("S3_ENDPOINT_URL")
    region = os.getenv("S3_REGION") or "us-east-1"
    access_key = os.getenv("S3_ACCESS_KEY")
    secret_key = os.getenv("S3_SECRET_KEY")
    use_ssl = _bool_env("S3_USE_SSL", endpoint_url is None)
    verify_ssl = _bool_env("S3_VERIFY_SSL", True)
    sse = _bool_env("S3_SSE", True)
    config = ObjectStoreConfig(
        bucket=bucket,
        prefix=prefix,
        endpoint_url=endpoint_url,
        region=region,
        access_key=access_key,
        secret_key=secret_key,
        use_ssl=use_ssl,
        verify_ssl=verify_ssl,
        sse=sse,
    )
    return ObjectStore(config)


def _bool_env(name: str, default: bool) -> bool:
    """Internal helper for bool env."""
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}
