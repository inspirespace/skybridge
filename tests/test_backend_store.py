"""Tests for backend storage helpers."""
from __future__ import annotations

import json
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from src.backend.models import FlightSummary, JobRecord, ReviewSummary
from src.backend.store import JobStore, _extract_locations, _extract_metadata_from_raw


def test_extract_metadata_from_raw_filters_empty_fields() -> None:
    """Test raw metadata extraction drops empty values."""
    raw_payload = {
        "flt": {
            "Meta": {
                "from": "KSEA",
                "to": "KLAX",
                "origin": "KSEA",
                "destination": "",
                "e_from": None,
            }
        }
    }

    extracted = _extract_metadata_from_raw(raw_payload)
    assert extracted == {
        "aircraft_from": "KSEA",
        "aircraft_to": "KLAX",
        "origin": "KSEA",
    }


def test_extract_locations_with_raw_loader() -> None:
    """Test origin/destination extraction falls back to raw payloads."""
    payload = {
        "items": [
            {
                "flight_id": "flight-1",
                "metadata": {},
                "raw_path": "flight-1.json",
            },
            {"flight_id": "", "metadata": {}},
            "invalid",
        ]
    }

    def raw_loader(_: str) -> dict:
        return {"flt": {"Meta": {"origin": "KSEA", "destination": "KLAX"}}}

    mapping = _extract_locations(payload, raw_loader=raw_loader)
    assert mapping["flight-1"] == ("KSEA", "KLAX")


def test_jobstore_enrich_review_summary_from_raw_payload() -> None:
    """Test review summary enrichment fills in missing locations."""
    with tempfile.TemporaryDirectory() as tmpdir:
        base_path = Path(tmpdir)
        store = JobStore(base_path)
        job_id = uuid4()
        now = datetime.now(timezone.utc)
        review_summary = ReviewSummary(
            flight_count=1,
            total_hours=1.0,
            missing_tail_numbers=0,
            flights=[
                FlightSummary(
                    flight_id="flight-1",
                    date="2026-01-05T10:00:00Z",
                    tail_number=None,
                    origin=None,
                    destination=None,
                    flight_time_minutes=None,
                    status=None,
                    message=None,
                )
            ],
        )
        job = JobRecord(
            job_id=job_id,
            user_id="pilot",
            status="review_ready",
            created_at=now,
            updated_at=now,
            review_summary=review_summary,
        )
        store.save_job(job)

        job_dir = base_path / str(job_id)
        review_payload = {
            "items": [
                {"flight_id": "flight-1", "metadata": {}, "raw_path": "flight-1.json"}
            ]
        }
        (job_dir / "review.json").write_text(json.dumps(review_payload))
        export_dir = job_dir / "cloudahoy_exports"
        export_dir.mkdir(parents=True, exist_ok=True)
        raw_payload = {"flt": {"Meta": {"origin": "KSEA", "destination": "KLAX"}}}
        (export_dir / "flight-1.json").write_text(json.dumps(raw_payload))

        loaded = store.load_job(job_id)
        assert loaded.review_summary is not None
        assert loaded.review_summary.flights[0].origin == "KSEA"
        assert loaded.review_summary.flights[0].destination == "KLAX"

        loaded_again = store.load_job(job_id)
        assert loaded_again.review_summary is not None
        assert loaded_again.review_summary.flights[0].origin == "KSEA"
        assert loaded_again.review_summary.flights[0].destination == "KLAX"


def test_jobstore_tokens_are_in_memory_only() -> None:
    """Ensure sensitive tokens are not persisted to disk."""
    with tempfile.TemporaryDirectory() as tmpdir:
        base_path = Path(tmpdir)
        store = JobStore(base_path)
        job_id = uuid4()
        store.write_token(job_id, "review", "secret-token")
        token_path = base_path / str(job_id) / "review.token"
        assert not token_path.exists()
        assert store.read_token(job_id, "review") == "secret-token"
        store.clear_token(job_id, "review")
        assert store.read_token(job_id, "review") is None


def test_jobstore_cleanup_expired_local() -> None:
    """Expired jobs are removed during cleanup."""
    with tempfile.TemporaryDirectory() as tmpdir:
        base_path = Path(tmpdir)
        store = JobStore(base_path)
        job_id = uuid4()
        now = datetime.now(timezone.utc)
        expired = now.replace(year=now.year - 2)
        job = JobRecord(
            job_id=job_id,
            user_id="pilot",
            status="review_ready",
            created_at=expired,
            updated_at=expired,
        )
        store.save_job(job)
        assert (base_path / str(job_id) / "job.json").exists()
        deleted = store.cleanup_expired()
        assert deleted == 1
        assert not (base_path / str(job_id) / "job.json").exists()
