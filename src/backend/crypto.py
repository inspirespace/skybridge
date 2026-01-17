"""Encryption helpers for sensitive payloads."""
from __future__ import annotations

import base64
import os
from typing import Any

from cryptography.fernet import Fernet, InvalidToken


def _load_key() -> bytes:
    key = os.getenv("BACKEND_ENCRYPTION_KEY")
    if not key:
        raise RuntimeError("BACKEND_ENCRYPTION_KEY is required for encrypted storage.")
    try:
        raw = key.encode("utf-8")
        # Fernet requires urlsafe base64-encoded 32-byte key.
        decoded = base64.urlsafe_b64decode(raw)
        if len(decoded) != 32:
            raise ValueError("Invalid key length.")
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError("BACKEND_ENCRYPTION_KEY must be a 32-byte urlsafe base64 key.") from exc
    return raw


def _fernet() -> Fernet:
    return Fernet(_load_key())


def require_encryption_key() -> None:
    """Validate the encryption key early for startup checks."""
    _load_key()


def encrypt_json(payload: dict[str, Any]) -> str:
    """Encrypt a JSON-serializable dict."""
    import json

    data = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    return _fernet().encrypt(data).decode("utf-8")


def decrypt_json(token: str) -> dict[str, Any]:
    """Decrypt a JSON payload."""
    import json

    try:
        raw = _fernet().decrypt(token.encode("utf-8"))
    except InvalidToken as exc:
        raise RuntimeError("Encrypted payload could not be decrypted.") from exc
    return json.loads(raw.decode("utf-8"))
