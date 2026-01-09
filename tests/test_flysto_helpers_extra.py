"""tests/test_flysto_helpers_extra.py module."""
from __future__ import annotations

from pathlib import Path

import pytest

from src.core.flysto.client import (
    _is_duplicate_upload_error,
    _metadata_payload,
    _normalize_role,
    _normalize_tag_list,
    _upload_url,
    _validate_flight_for_upload,
)
from src.core.models import FlightDetail


def test_normalize_role_and_tags():
    assert _normalize_role(" Pilot In Command ") == "pilotincommand"
    assert _normalize_tag_list("a, b , ,c") == ["a", "b", "c"]
    assert _normalize_tag_list(["a", "", None, "b"]) == ["a", "b"]
    assert _normalize_tag_list(None) == []


def test_duplicate_upload_error_detection():
    assert _is_duplicate_upload_error(409, None) is True
    assert _is_duplicate_upload_error(400, "Already exists") is True
    assert _is_duplicate_upload_error(400, "Other error") is False


def test_upload_url_building():
    assert _upload_url(None, "https://flysto", "flight.gpx") == "https://flysto/api/log-upload?id=flight.gpx@@@0"
    assert _upload_url("https://flysto/api/log-upload?foo=1", "https://flysto", "flight.gpx") == "https://flysto/api/log-upload?foo=1"


def test_metadata_payload_and_validation(tmp_path: Path):
    file_path = tmp_path / "f1.gpx"
    file_path.write_text("data")
    flight = FlightDetail(
        id="f1",
        raw_payload={"flt": {"Meta": {"pilot": "Ada"}}},
        file_path=str(file_path),
    )
    assert _metadata_payload(flight) == {"pilot": "Ada"}
    with pytest.raises(RuntimeError):
        _validate_flight_for_upload(FlightDetail(id="f2", raw_payload={}))
