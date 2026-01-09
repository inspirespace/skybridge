"""Extra coverage tests for JobStore helpers."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4
import json

import pytest

from src.backend.models import FlightSummary, JobRecord, ReviewSummary
from src.backend.store import (
    JobStore,
    _bool_env,
    _coerce_location,
    _extract_locations,
    _ttl_epoch,
)


class FakeObjectStore:
    def __init__(self) -> None:
        self.payloads: dict[str, dict] = {}

    def key_for(self, *parts: str) -> str:
        return "/".join(parts)

    def list_prefix(self, _prefix: str) -> list[str]:
        return ["review.json", "import_report.json"]

    def get_json(self, key: str):
        return self.payloads.get(key)

    def put_json(self, key: str, payload: dict) -> None:
        self.payloads[key] = payload

    def put_file(self, _key: str, _path: Path) -> None:
        return None

    def delete_prefix(self, _prefix: str) -> None:
        return None


def _job_record(job_id, user_id: str = "user-1") -> JobRecord:
    now = datetime.now(timezone.utc)
    return JobRecord(
        job_id=job_id,
        user_id=user_id,
        status="review_ready",
        created_at=now,
        updated_at=now,
        review_summary=ReviewSummary(
            flight_count=1,
            total_hours=1.0,
            flights=[
                FlightSummary(
                    flight_id="F1",
                    date="2026-01-01",
                    origin=None,
                    destination=None,
                )
            ],
        ),
    )


def test_extract_locations_prefers_metadata_and_raw_loader(tmp_path: Path):
    raw_path = tmp_path / "raw.json"
    raw_path.write_text(
        json.dumps(
            {
                "flt": {
                    "Meta": {
                        "origin": "KPAO",
                        "destination": "KSJC",
                    }
                }
            }
        )
    )
    payload = {
        "items": [
            {
                "flight_id": "F1",
                "metadata": {"origin": "KSFO"},
                "raw_path": str(raw_path),
            }
        ]
    }
    mapping = _extract_locations(payload, raw_loader=lambda path: json.loads(Path(path).read_text()))
    assert mapping["F1"] == ("KSFO", "KSJC")


def test_coerce_location_handles_dicts():
    assert _coerce_location("KAPA") == "KAPA"
    assert _coerce_location({"c": "KPAO", "t": "Palo Alto"}) == "KPAO"
    assert _coerce_location({"t": "Palo Alto"}) == "Palo Alto"
    assert _coerce_location({}) is None


def test_enrich_review_summary_from_review_payload(tmp_path: Path):
    store = JobStore(tmp_path)
    job = _job_record(uuid4())
    store.save_job(job)
    review_payload = {
        "items": [
            {
                "flight_id": "F1",
                "metadata": {"origin": "KPAO", "destination": "KSJC"},
            }
        ]
    }
    (store.job_dir(job.job_id) / "review.json").write_text(json.dumps(review_payload))

    loaded = store.load_job(job.job_id)
    flight = loaded.review_summary.flights[0]
    assert flight.origin == "KPAO"
    assert flight.destination == "KSJC"


def test_enrich_review_summary_from_raw_payload(tmp_path: Path):
    store = JobStore(tmp_path)
    job = _job_record(uuid4())
    store.save_job(job)

    raw_path = tmp_path / "raw.json"
    raw_path.write_text(
        json.dumps(
            {
                "flt": {
                    "Meta": {
                        "origin": "EHAM",
                        "destination": "EDDF",
                    }
                }
            }
        )
    )
    review_payload = {
        "items": [
            {
                "flight_id": "F1",
                "metadata": {},
                "raw_path": str(raw_path),
            }
        ]
    }
    (store.job_dir(job.job_id) / "review.json").write_text(json.dumps(review_payload))

    loaded = store.load_job(job.job_id)
    flight = loaded.review_summary.flights[0]
    assert flight.origin == "EHAM"
    assert flight.destination == "EDDF"


def test_token_lifecycle(tmp_path: Path):
    store = JobStore(tmp_path)
    job = _job_record(uuid4())
    store.save_job(job)

    store.write_token(job.job_id, "review", "tok-1")
    assert store.read_token(job.job_id, "review") == "tok-1"
    store.clear_token(job.job_id, "review")
    assert store.read_token(job.job_id, "review") is None


def test_list_all_jobs_expires_old_entries(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    store = JobStore(tmp_path)
    job = _job_record(uuid4())
    old = job.model_copy(update={"created_at": datetime.now(timezone.utc) - timedelta(days=10)})
    store.save_job(old)
    monkeypatch.setenv("BACKEND_RETENTION_DAYS", "1")

    jobs = store.list_all_jobs()
    assert jobs == []
    assert not store.job_dir(old.job_id).exists()


def test_load_artifact_falls_back_to_object_store(tmp_path: Path):
    object_store = FakeObjectStore()
    store = JobStore(tmp_path, object_store=object_store)
    job = _job_record(uuid4())
    store.save_job(job)

    key = object_store.key_for(job.user_id, str(job.job_id), "summary.json")
    object_store.put_json(key, {"ok": True})

    payload = store.load_artifact(job.job_id, "summary.json")
    assert payload == {"ok": True}


def test_bool_env_and_ttl_epoch(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("BACKEND_RETENTION_DAYS", "3")
    created_at = datetime(2026, 1, 1, tzinfo=timezone.utc)
    ttl = _ttl_epoch(created_at)
    assert ttl > int(created_at.timestamp())

    monkeypatch.setenv("FLAG", "yes")
    assert _bool_env("FLAG", False) is True
    monkeypatch.setenv("FLAG", "0")
    assert _bool_env("FLAG", True) is False
