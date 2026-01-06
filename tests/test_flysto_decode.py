"""tests/test_flysto_decode.py module."""
from __future__ import annotations

import json

from src.core.flysto.client import _decode_flysto_payload, _swap_chars


def test_decode_flysto_payload_handles_wait_prefix():
    """Test decode flysto payload handles wait prefix."""
    payload = {"ok": True, "items": [1, 2]}
    encoded = json.dumps({"RESPONSE": _swap_chars(json.dumps(payload))})
    decoded = _decode_flysto_payload("wait\n" + encoded)
    assert isinstance(decoded, str)
    assert json.loads(decoded) == payload


def test_decode_flysto_payload_passthrough_json():
    """Test decode flysto payload passthrough json."""
    payload = {"hello": "world"}
    decoded = _decode_flysto_payload(json.dumps(payload))
    assert decoded == payload
