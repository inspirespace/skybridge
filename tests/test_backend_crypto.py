"""Tests for backend crypto helpers."""
from __future__ import annotations

from cryptography.fernet import Fernet

import src.backend.crypto as crypto


def test_encrypt_decrypt_roundtrip(monkeypatch):
    key = Fernet.generate_key().decode("utf-8")
    monkeypatch.setenv("BACKEND_ENCRYPTION_KEY", key)
    payload = {"user": "pilot", "token": "secret"}
    encrypted = crypto.encrypt_json(payload)
    assert isinstance(encrypted, str)
    assert "secret" not in encrypted
    assert crypto.decrypt_json(encrypted) == payload


def test_invalid_key_rejected(monkeypatch):
    monkeypatch.setenv("BACKEND_ENCRYPTION_KEY", "not-a-key")
    try:
        crypto.encrypt_json({"a": 1})
    except RuntimeError as exc:
        assert "BACKEND_ENCRYPTION_KEY" in str(exc)
    else:
        raise AssertionError("Expected RuntimeError for invalid key")
