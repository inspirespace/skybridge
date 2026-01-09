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
        now = datetime(2026, 1, 5, 10, 0, tzinfo=timezone.utc)
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
