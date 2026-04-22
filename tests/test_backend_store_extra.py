"""Extra tests for backend store helpers."""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from shutil import rmtree
from pathlib import Path
from uuid import UUID

import pytest

from src.backend.models import FlightSummary, JobRecord, ReviewSummary
from src.backend.store import (
    JobStore,
    _coerce_location,
    _extract_locations,
    _extract_metadata_from_raw,
    _serialize,
    _ttl_epoch,
)


class FakeObjectStore:
    def __init__(self):
        self.json_payloads = {}
        self.files = []
        self.deleted_prefixes = []

    def key_for(self, user_id: str, job_id: str, name: str | None = None) -> str:
        if name:
            return f"{user_id}/{job_id}/{name}"
        return f"{user_id}/{job_id}"

    def put_json(self, key: str, payload: dict) -> None:
        self.json_payloads[key] = payload

    def get_json(self, key: str):
        return self.json_payloads.get(key)

    def put_file(self, key: str, path: Path) -> None:
        self.files.append((key, path))

    def download_to_file(self, _key: str, _file_obj) -> bool:
        return False

    def list_prefix(self, prefix: str):
        return [key.split("/")[-1] for key in self.json_payloads if key.startswith(prefix)]

    def delete_prefix(self, prefix: str):
        self.deleted_prefixes.append(prefix)


@pytest.fixture
def job_record() -> JobRecord:
    now = datetime.now(timezone.utc)
    return JobRecord(
        job_id=UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"),
        user_id="user-1",
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
                    tail_number="N1",
                    origin=None,
                    destination=None,
                )
            ],
        ),
    )
def test_ttl_epoch_handles_naive_datetime(monkeypatch):
    naive = datetime(2026, 1, 1)
    monkeypatch.setenv("BACKEND_RETENTION_DAYS", "1")
    ttl = _ttl_epoch(naive)
    assert ttl == int(naive.replace(tzinfo=timezone.utc).timestamp() + 86400)


def test_extract_metadata_from_raw_and_locations():
    raw = {"flt": {"Meta": {"from": "KPAE", "to": "KBFI", "origin": "KPAE"}}}
    meta = _extract_metadata_from_raw(raw)
    assert meta["aircraft_from"] == "KPAE"

    payload = {
        "items": [
            {
                "flight_id": "F1",
                "metadata": {"origin": {"c": "KPAE"}, "destination": {"t": "Boeing"}},
            }
        ]
    }
    mapping = _extract_locations(payload)
    assert mapping["F1"] == ("KPAE", "Boeing")


def test_extract_locations_uses_raw_loader():
    payload = {"items": [{"flight_id": "F1", "raw_path": "raw.json"}]}

    def raw_loader(_path: str):
        return {"flt": {"Meta": {"from": "KPAE", "to": "KBFI"}}}

    mapping = _extract_locations(payload, raw_loader=raw_loader)
    assert mapping["F1"] == ("KPAE", "KBFI")


def test_coerce_location():
    assert _coerce_location("KPAE") == "KPAE"
    assert _coerce_location({"t": "Paine"}) == "Paine"
    assert _coerce_location({"c": "KPAE"}) == "KPAE"
    assert _coerce_location(123) is None


def test_serialize_converts_types(job_record):
    payload = _serialize(job_record)
    assert payload["job_id"] == "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
    assert payload["review_summary"]["flight_count"] == 1


def test_list_artifacts_with_object_store(tmp_path, job_record):
    store = JobStore(tmp_path, object_store=FakeObjectStore())
    store.save_job(job_record)
    key = store.object_store.key_for(job_record.user_id, str(job_record.job_id), "review.json")
    store.object_store.put_json(key, {"items": []})

    artifacts = store.list_artifacts(job_record.job_id)
    assert "review.json" in artifacts


def test_list_artifacts_merges_local_and_object_store(tmp_path, job_record):
    object_store = FakeObjectStore()
    store = JobStore(tmp_path, object_store=object_store)
    store.save_job(job_record)
    (tmp_path / str(job_record.job_id) / "local.json").write_text(json.dumps({"ok": True}))
    key = object_store.key_for(job_record.user_id, str(job_record.job_id), "review.json")
    object_store.put_json(key, {"items": []})

    artifacts = store.list_artifacts(job_record.job_id)
    assert "local.json" in artifacts
    assert "review.json" in artifacts


def test_load_artifact_with_object_store(tmp_path, job_record):
    store = JobStore(tmp_path, object_store=FakeObjectStore())
    store.save_job(job_record)
    key = store.object_store.key_for(job_record.user_id, str(job_record.job_id), "review.json")
    store.object_store.put_json(key, {"items": []})

    payload = store.load_artifact(job_record.job_id, "review.json")
    assert payload == {"items": []}


def test_upload_artifact_dir_filters_suffix(tmp_path, job_record):
    object_store = FakeObjectStore()
    store = JobStore(tmp_path, object_store=object_store)
    store.save_job(job_record)

    export_dir = tmp_path / str(job_record.job_id) / "exports"
    export_dir.mkdir(parents=True)
    (export_dir / "one.gpx").write_text("one")
    (export_dir / "two.csv").write_text("two")

    store.upload_artifact_dir(job_record.job_id, prefix="exports", directory=export_dir, suffix=".gpx")
    assert any(key.endswith("one.gpx") for key, _ in object_store.files)
    assert not any(key.endswith("two.csv") for key, _ in object_store.files)


def test_maybe_enrich_review_summary(tmp_path, job_record):
    store = JobStore(tmp_path)
    store.save_job(job_record)
    review_payload = {
        "items": [
            {
                "flight_id": "F1",
                "metadata": {"event_from": "KPAE", "event_to": "KBFI"},
            }
        ]
    }
    (tmp_path / str(job_record.job_id) / "review.json").write_text(json.dumps(review_payload))

    enriched = store._maybe_enrich_review_summary(job_record)
    flight = enriched.review_summary.flights[0]
    assert flight.origin == "KPAE"
    assert flight.destination == "KBFI"
