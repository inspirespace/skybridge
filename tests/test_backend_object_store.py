"""Tests for backend object store helper."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import boto3
import pytest
from botocore.exceptions import ClientError

from src.backend.object_store import (
    ObjectStore,
    ObjectStoreConfig,
    _bool_env,
    build_object_store_from_env,
)


def _client_error(operation: str) -> ClientError:
    return ClientError({"Error": {"Code": "404", "Message": "Not Found"}}, operation)


class FakeBody:
    def __init__(self, data: bytes) -> None:
        self._data = data

    def read(self) -> bytes:
        return self._data


class FakePaginator:
    def __init__(self, client: "FakeS3") -> None:
        self._client = client

    def paginate(self, Bucket: str, Prefix: str):
        contents = [
            {"Key": key}
            for key in sorted(self._client.objects)
            if key.startswith(Prefix)
        ]
        return [{"Contents": contents}]


class FakeS3:
    def __init__(self) -> None:
        self.objects: dict[str, bytes] = {}
        self.created_bucket: dict | None = None
        self.last_put_extra: dict | None = None
        self.last_upload_extra: dict | None = None
        self.deleted: list[dict] = []

    def head_bucket(self, Bucket: str) -> None:
        raise _client_error("HeadBucket")

    def create_bucket(self, **kwargs) -> None:
        self.created_bucket = kwargs

    def put_object(self, Bucket: str, Key: str, Body: bytes, **extra) -> None:
        self.objects[Key] = Body
        self.last_put_extra = extra

    def upload_file(self, filename: str, bucket: str, key: str, ExtraArgs=None) -> None:
        self.objects[key] = Path(filename).read_bytes()
        self.last_upload_extra = ExtraArgs

    def get_object(self, Bucket: str, Key: str):
        if Key not in self.objects:
            raise _client_error("GetObject")
        return {"Body": FakeBody(self.objects[Key])}

    def get_paginator(self, name: str) -> FakePaginator:
        assert name == "list_objects_v2"
        return FakePaginator(self)

    def delete_objects(self, Bucket: str, Delete: dict) -> None:
        self.deleted.append(Delete)
        for item in Delete.get("Objects", []):
            key = item.get("Key")
            if key in self.objects:
                self.objects.pop(key, None)


class FakeS3HeadOk(FakeS3):
    def head_bucket(self, Bucket: str) -> None:
        return None


class FakeS3EmptyBody(FakeS3):
    def get_object(self, Bucket: str, Key: str):
        return {"Body": None}


class FakePaginatorMissingKey:
    def paginate(self, Bucket: str, Prefix: str):
        return [{"Contents": [{"Key": None}, {}]}]


class FakeS3MissingKey(FakeS3):
    def get_paginator(self, name: str):
        assert name == "list_objects_v2"
        return FakePaginatorMissingKey()


@dataclass(frozen=True)
class StoreFixture:
    store: ObjectStore
    client: FakeS3


def build_store(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> StoreFixture:
    """Build ObjectStore with a fake S3 client."""
    fake = FakeS3()
    monkeypatch.setattr(boto3, "client", lambda *args, **kwargs: fake)
    config = ObjectStoreConfig(
        bucket="test-bucket",
        prefix="jobs",
        endpoint_url=None,
        region="us-east-1",
        access_key=None,
        secret_key=None,
        use_ssl=True,
        verify_ssl=True,
        sse=True,
    )
    return StoreFixture(store=ObjectStore(config), client=fake)


def test_object_store_put_get_list_delete(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Test object store CRUD flow for JSON and file artifacts."""
    fixture = build_store(monkeypatch, tmp_path)
    store = fixture.store
    client = fixture.client

    key = store.key_for("user", "job", "review.json")
    store.put_json(key, {"ok": True})
    assert client.last_put_extra is not None
    assert client.last_put_extra.get("ServerSideEncryption") == "AES256"
    assert store.get_json(key) == {"ok": True}

    file_path = tmp_path / "artifact.txt"
    file_path.write_text("payload")
    upload_key = store.key_for("user", "job", "artifact.txt")
    store.put_file(upload_key, file_path)
    assert store.get_bytes(upload_key) == b"payload"
    assert client.last_upload_extra == {"ServerSideEncryption": "AES256"}

    prefix = store.key_for("user", "job")
    listed = store.list_prefix(prefix)
    assert listed == ["artifact.txt", "review.json"]

    store.delete_prefix(prefix)
    assert client.objects == {}


def test_object_store_key_for_empty_prefix(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = FakeS3()
    monkeypatch.setattr(boto3, "client", lambda *args, **kwargs: fake)
    config = ObjectStoreConfig(
        bucket="test-bucket",
        prefix="",
        endpoint_url=None,
        region="us-east-1",
        access_key=None,
        secret_key=None,
        use_ssl=True,
        verify_ssl=True,
        sse=False,
    )
    store = ObjectStore(config)
    assert store.key_for("user", "job", "review.json") == "user/job/review.json"


def test_object_store_get_json_missing_returns_none(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = FakeS3()
    monkeypatch.setattr(boto3, "client", lambda *args, **kwargs: fake)
    store = ObjectStore(
        ObjectStoreConfig(
            bucket="test-bucket",
            prefix="jobs",
            endpoint_url=None,
            region="us-east-1",
            access_key=None,
            secret_key=None,
            use_ssl=True,
            verify_ssl=True,
            sse=False,
        )
    )
    assert store.get_json("missing.json") is None
    assert store.get_bytes("missing.json") is None


def test_object_store_get_json_empty_body_returns_none(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = FakeS3EmptyBody()
    monkeypatch.setattr(boto3, "client", lambda *args, **kwargs: fake)
    store = ObjectStore(
        ObjectStoreConfig(
            bucket="test-bucket",
            prefix="jobs",
            endpoint_url=None,
            region="us-east-1",
            access_key=None,
            secret_key=None,
            use_ssl=True,
            verify_ssl=True,
            sse=False,
        )
    )
    assert store.get_json("empty.json") is None
    assert store.get_bytes("empty.json") is None


def test_object_store_list_prefix_skips_missing_keys(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = FakeS3MissingKey()
    monkeypatch.setattr(boto3, "client", lambda *args, **kwargs: fake)
    store = ObjectStore(
        ObjectStoreConfig(
            bucket="test-bucket",
            prefix="jobs",
            endpoint_url=None,
            region="us-east-1",
            access_key=None,
            secret_key=None,
            use_ssl=True,
            verify_ssl=True,
            sse=False,
        )
    )
    assert store.list_prefix("jobs/user/job") == []


def test_object_store_delete_prefix_noop_on_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = FakeS3MissingKey()
    monkeypatch.setattr(boto3, "client", lambda *args, **kwargs: fake)
    store = ObjectStore(
        ObjectStoreConfig(
            bucket="test-bucket",
            prefix="jobs",
            endpoint_url=None,
            region="us-east-1",
            access_key=None,
            secret_key=None,
            use_ssl=True,
            verify_ssl=True,
            sse=False,
        )
    )
    store.delete_prefix("jobs/user/job")
    assert fake.deleted == []


def test_object_store_ensure_bucket_skips_create_on_existing(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = FakeS3HeadOk()
    monkeypatch.setattr(boto3, "client", lambda *args, **kwargs: fake)
    store = ObjectStore(
        ObjectStoreConfig(
            bucket="test-bucket",
            prefix="jobs",
            endpoint_url=None,
            region="us-east-1",
            access_key=None,
            secret_key=None,
            use_ssl=True,
            verify_ssl=True,
            sse=False,
        )
    )
    assert store.bucket == "test-bucket"
    assert fake.created_bucket is None


def test_build_object_store_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = FakeS3()
    monkeypatch.setattr(boto3, "client", lambda *args, **kwargs: fake)
    monkeypatch.setenv("BACKEND_S3_ENABLED", "1")
    monkeypatch.setenv("S3_BUCKET", "env-bucket")
    monkeypatch.setenv("S3_PREFIX", "env-prefix")
    monkeypatch.setenv("S3_ENDPOINT_URL", "http://s3.local")
    monkeypatch.setenv("S3_REGION", "eu-west-1")
    monkeypatch.setenv("S3_ACCESS_KEY", "access")
    monkeypatch.setenv("S3_SECRET_KEY", "secret")
    monkeypatch.setenv("S3_USE_SSL", "0")
    monkeypatch.setenv("S3_VERIFY_SSL", "0")
    monkeypatch.setenv("S3_SSE", "0")

    store = build_object_store_from_env()
    assert store is not None
    assert store.bucket == "env-bucket"
    assert store.key_for("user") == "env-prefix/user"


def test_bool_env_default_and_values(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("SOME_FLAG", raising=False)
    assert _bool_env("SOME_FLAG", True) is True
    monkeypatch.setenv("SOME_FLAG", "true")
    assert _bool_env("SOME_FLAG", False) is True
    monkeypatch.setenv("SOME_FLAG", "0")
    assert _bool_env("SOME_FLAG", True) is False
