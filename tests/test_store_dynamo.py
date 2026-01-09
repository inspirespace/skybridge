"""Coverage for JobStore DynamoDB paths."""
from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4
import json

import pytest

from src.backend.models import JobRecord
from src.backend.store import JobStore, _serialize


class FakeDynamoTable:
    def __init__(self) -> None:
        self.items: dict[tuple[str, str], dict] = {}
        self.deleted: list[tuple[str, str]] = []

    def put_item(self, Item):
        key = (Item["user_id"], Item["job_id"])
        self.items[key] = Item

    def scan(self, **_kwargs):
        return {"Items": list(self.items.values())}

    def query(self, **_kwargs):
        return {"Items": list(self.items.values())}

    def delete_item(self, Key):
        key = (Key["user_id"], Key["job_id"])
        self.items.pop(key, None)
        self.deleted.append(key)

    def update_item(self, Key, UpdateExpression=None, ExpressionAttributeValues=None):
        key = (Key["user_id"], Key["job_id"])
        item = self.items.get(key)
        if not item:
            return
        if UpdateExpression and UpdateExpression.startswith("SET"):
            field = UpdateExpression.split("SET", 1)[1].strip().split(" ")[0]
            value = ExpressionAttributeValues[":token"]
            payload = json.loads(item.get("payload", "{}"))
            payload[field] = value
            item["payload"] = json.dumps(payload)
        if UpdateExpression and UpdateExpression.startswith("REMOVE"):
            field = UpdateExpression.split("REMOVE", 1)[1].strip()
            payload = json.loads(item.get("payload", "{}"))
            payload.pop(field, None)
            item["payload"] = json.dumps(payload)

    def get_item(self, Key, ProjectionExpression=None):
        key = (Key["user_id"], Key["job_id"])
        item = self.items.get(key)
        if not item:
            return {}
        payload = json.loads(item.get("payload", "{}"))
        if ProjectionExpression:
            return {"Item": {ProjectionExpression: payload.get(ProjectionExpression)}}
        return {"Item": payload}


def _job_record() -> JobRecord:
    now = datetime.now(timezone.utc)
    return JobRecord(
        job_id=uuid4(),
        user_id="user-1",
        status="review_ready",
        created_at=now,
        updated_at=now,
    )


def test_dynamo_save_and_load(monkeypatch: pytest.MonkeyPatch, tmp_path):
    store = JobStore(tmp_path)
    table = FakeDynamoTable()
    store._dynamo_table = table

    job = _job_record()
    store.save_job(job)

    loaded = store.load_job(job.job_id)
    assert loaded.job_id == job.job_id


def test_dynamo_token_read_write(monkeypatch: pytest.MonkeyPatch, tmp_path):
    store = JobStore(tmp_path)
    table = FakeDynamoTable()
    store._dynamo_table = table

    job = _job_record()
    store.save_job(job)

    store.write_token(job.job_id, "review", "token")
    token_file = store.job_dir(job.job_id) / "review.token"
    token_file.unlink()

    assert store.read_token(job.job_id, "review") == "token"
    store.clear_token(job.job_id, "review")
    assert store.read_token(job.job_id, "review") is None


def test_dynamo_list_and_delete(monkeypatch: pytest.MonkeyPatch, tmp_path):
    store = JobStore(tmp_path)
    table = FakeDynamoTable()
    store._dynamo_table = table

    job = _job_record()
    payload = json.dumps(_serialize(job))
    table.put_item(
        {
            "user_id": job.user_id,
            "job_id": str(job.job_id),
            "payload": payload,
            "created_at": job.created_at.isoformat(),
            "updated_at": job.updated_at.isoformat(),
            "ttl_epoch": 0,
        }
    )

    jobs = store.list_jobs(job.user_id)
    assert jobs

    store.delete_job(job.job_id, user_id=job.user_id)
    assert table.deleted
