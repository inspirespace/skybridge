"""Coverage for worker run loops."""
from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4
import json

import pytest

import src.backend.worker as worker
from src.backend.models import JobRecord


class FakeStore:
    def __init__(self, *args, **kwargs) -> None:
        now = datetime.now(timezone.utc)
        self.jobs = [
            JobRecord(
                job_id=uuid4(),
                user_id="user-1",
                status="review_queued",
                created_at=now,
                updated_at=now,
            ),
            JobRecord(
                job_id=uuid4(),
                user_id="user-1",
                status="import_queued",
                created_at=now,
                updated_at=now,
            ),
        ]

    def list_all_jobs(self):
        return self.jobs

    def load_job(self, job_id):
        for job in self.jobs:
            if job.job_id == job_id:
                return job
        raise FileNotFoundError("job not found")

    def save_job(self, job):
        return None


class FakeSQS:
    def __init__(self) -> None:
        self.calls = 0
        self.deleted = 0

    def receive_message(self, **_kwargs):
        self.calls += 1
        if self.calls > 1:
            raise SystemExit
        payload = {
            "job_id": str(uuid4()),
            "purpose": "review",
            "token": "tok",
        }
        return {"Messages": [{"Body": json.dumps(payload), "ReceiptHandle": "r1"}]}

    def delete_message(self, **_kwargs):
        self.deleted += 1


def test_run_processes_queue_message(monkeypatch: pytest.MonkeyPatch, tmp_path):
    fake_sqs = FakeSQS()
    monkeypatch.setattr(worker, "_use_queue", lambda: True)
    monkeypatch.setattr(worker, "_queue_url", lambda: "queue-url")
    monkeypatch.setattr(worker, "_get_sqs_client", lambda: fake_sqs)
    monkeypatch.setattr(worker, "_handle_job", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(worker, "JobStore", lambda *_args, **_kwargs: FakeStore())
    monkeypatch.setattr(worker, "build_object_store_from_env", lambda: None)
    monkeypatch.setattr(worker, "_dynamo_jobs_table", lambda: None)

    with pytest.raises(SystemExit):
        worker.run()
    assert fake_sqs.deleted == 1


def test_run_dev_loop_handles_jobs(monkeypatch: pytest.MonkeyPatch, tmp_path):
    handled = {"count": 0}

    def fake_handle(_store, _job_id, _purpose, _token):
        handled["count"] += 1

    monkeypatch.setattr(worker, "_use_queue", lambda: False)
    monkeypatch.setattr(worker, "JobStore", lambda *_args, **_kwargs: FakeStore())
    monkeypatch.setattr(worker, "build_object_store_from_env", lambda: None)
    monkeypatch.setattr(worker, "_dynamo_jobs_table", lambda: None)
    monkeypatch.setattr(worker, "_handle_job", fake_handle)
    monkeypatch.setattr(worker.time, "sleep", lambda _sec: (_ for _ in ()).throw(SystemExit()))

    with pytest.raises(SystemExit):
        worker.run()
    assert handled["count"] == 2
