from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.flysto.client import _parse_signature_field, _parse_upload_response


def test_parse_upload_signature_from_fixture():
    report = Path("data/runs/20251228T185601Z/import_report.json")
    if not report.exists():
        pytest.skip("fixture run not available")
    data = json.loads(report.read_text())
    item = data.get("items", [])[0]
    signature = item.get("flysto_upload_signature")
    filename = Path(item.get("file_path", "flight.g3x.csv")).name
    assert isinstance(signature, str)

    parsed = _parse_upload_response(json.dumps({"signature": signature}), filename)
    assert parsed is not None
    assert parsed.signature == signature
    assert parsed.log_id == signature.split("/")[-1]
    assert parsed.signature_hash == signature.split("/")[-2]


def test_parse_signature_field_with_raw_value():
    sig = "flight.g3x.csv/dbb6797c/371885"
    signature, log_id, sig_hash = _parse_signature_field(sig, "flight.g3x.csv")
    assert signature == sig
    assert log_id == "371885"
    assert sig_hash == "dbb6797c"


def test_parse_upload_response_with_log_fields():
    payload = {
        "signature": "flight.gpx/hash999/log555",
        "logId": "log555",
        "format": "GenericGpx",
    }
    parsed = _parse_upload_response(json.dumps(payload), "flight.gpx")
    assert parsed is not None
    assert parsed.signature == payload["signature"]
    assert parsed.log_id == "log555"
    assert parsed.log_format == "GenericGpx"
    assert parsed.signature_hash == "hash999"


def test_parse_signature_field_two_parts():
    sig = "flight.g3x.csv/dbb6797c"
    signature, log_id, sig_hash = _parse_signature_field(sig, "flight.g3x.csv")
    assert signature == sig
    assert log_id is None
    assert sig_hash == "dbb6797c"
