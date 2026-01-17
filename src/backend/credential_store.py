"""Short-lived credential store for worker jobs.

Credentials are issued with a TTL and can be claimed once by the worker.
Backed by in-memory dict (dev) or Firestore (GCP).
"""
from __future__ import annotations

import secrets
import time
import os
from datetime import datetime, timezone
from dataclasses import dataclass
from typing import Optional

from .crypto import decrypt_json, encrypt_json, require_encryption_key

@dataclass
class _Entry:
    job_id: str
    purpose: str
    credentials: dict
    expires_at: float
    used: bool = False


class CredentialStore:
    def __init__(self) -> None:
        """Internal helper for init  ."""
        self._entries: dict[str, _Entry] = {}

    def issue(self, job_id: str, purpose: str, credentials: dict, ttl_seconds: int) -> str:
        """Handle issue."""
        token = secrets.token_urlsafe(32)
        self._entries[token] = _Entry(
            job_id=job_id,
            purpose=purpose,
            credentials=credentials,
            expires_at=time.time() + ttl_seconds,
        )
        return token

    def claim(self, token: str, job_id: str, purpose: str) -> Optional[dict]:
        """Handle claim."""
        entry = self._entries.get(token)
        if not entry:
            return None
        if entry.used or entry.job_id != job_id or entry.purpose != purpose:
            return None
        if time.time() > entry.expires_at:
            self._entries.pop(token, None)
            return None
        entry.used = True
        self._entries.pop(token, None)
        return entry.credentials


class FirestoreCredentialStore:
    def __init__(self, collection: str, project_id: str | None = None) -> None:
        """Internal helper for init  ."""
        from google.cloud import firestore

        require_encryption_key()
        self._client = firestore.Client(project=project_id or None)
        self._collection = self._client.collection(collection)

    def issue(self, job_id: str, purpose: str, credentials: dict, ttl_seconds: int) -> str:
        """Handle issue."""
        token = secrets.token_urlsafe(32)
        encrypted = encrypt_json(credentials)
        ttl_epoch = int(time.time() + ttl_seconds)
        ttl_at = datetime.fromtimestamp(ttl_epoch, tz=timezone.utc)
        self._collection.document(token).set(
            {
                "job_id": job_id,
                "purpose": purpose,
                "credentials_enc": encrypted,
                "enc_v": 1,
                "ttl_epoch": ttl_epoch,
                "ttl_at": ttl_at,
                "used": False,
            }
        )
        return token

    def claim(self, token: str, job_id: str, purpose: str) -> Optional[dict]:
        """Handle claim."""
        from google.cloud import firestore

        doc_ref = self._collection.document(token)

        @firestore.transactional
        def _claim(txn):
            snapshot = doc_ref.get(transaction=txn)
            if not snapshot.exists:
                return None
            item = snapshot.to_dict() or {}
            if item.get("used") or item.get("job_id") != job_id or item.get("purpose") != purpose:
                return None
            if time.time() > int(item.get("ttl_epoch") or 0):
                txn.delete(doc_ref)
                return None
            txn.delete(doc_ref)
            encrypted = item.get("credentials_enc")
            if not encrypted:
                return None
            return decrypt_json(encrypted)

        transaction = self._client.transaction()
        return _claim(transaction)


def build_credential_store() -> CredentialStore | FirestoreCredentialStore:
    """Build credential store."""
    if (os.getenv("BACKEND_FIRESTORE_ENABLED") or "false").lower() in {"1", "true", "yes", "on"}:
        collection = os.getenv("FIRESTORE_CREDENTIALS_COLLECTION") or "skybridge-credentials"
        project_id = os.getenv("GCP_PROJECT_ID") or os.getenv("GOOGLE_CLOUD_PROJECT")
        return FirestoreCredentialStore(collection, project_id)
    return CredentialStore()
