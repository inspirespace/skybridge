"""Short-lived credential store for worker jobs."""
from __future__ import annotations

import os
import secrets
import time
from datetime import datetime, timezone
from dataclasses import dataclass
from typing import Optional

from .crypto import decrypt_json, encrypt_json, require_encryption_key
from .env import resolve_project_id
from .firebase_errors import raise_if_missing_firestore_database

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
        self._job_credentials: dict[str, _Entry] = {}

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

    def store_job_credentials(self, job_id: str, credentials: dict, ttl_seconds: int) -> None:
        """Persist reusable job-scoped credentials for explicit user-triggered actions."""
        self._job_credentials[job_id] = _Entry(
            job_id=job_id,
            purpose="job",
            credentials=credentials,
            expires_at=time.time() + ttl_seconds,
        )

    def load_job_credentials(self, job_id: str) -> Optional[dict]:
        """Load job-scoped credentials when still valid."""
        entry = self._job_credentials.get(job_id)
        if not entry:
            return None
        if time.time() > entry.expires_at:
            self._job_credentials.pop(job_id, None)
            return None
        return entry.credentials

    def delete_job_credentials(self, job_id: str) -> None:
        """Delete any reusable credentials associated with a job."""
        self._job_credentials.pop(job_id, None)


class FirestoreCredentialStore:
    def __init__(self, collection: str, project_id: str | None = None) -> None:
        """Internal helper for init  ."""
        from google.cloud import firestore

        require_encryption_key()
        self._project_id = project_id
        self._database_id = "(default)"
        self._client = firestore.Client(project=project_id or None)
        self._collection = self._client.collection(collection)

    def _raise_firestore_configuration_error(self, exc: Exception) -> None:
        """Translate Firestore database lookup failures to config errors."""
        raise_if_missing_firestore_database(
            exc,
            project_id=self._project_id,
            database_id=self._database_id,
        )

    def issue(self, job_id: str, purpose: str, credentials: dict, ttl_seconds: int) -> str:
        """Handle issue."""
        token = secrets.token_urlsafe(32)
        encrypted = encrypt_json(credentials)
        ttl_epoch = int(time.time() + ttl_seconds)
        ttl_at = datetime.fromtimestamp(ttl_epoch, tz=timezone.utc)
        try:
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
        except Exception as exc:
            self._raise_firestore_configuration_error(exc)
            raise
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
        try:
            return _claim(transaction)
        except Exception as exc:
            self._raise_firestore_configuration_error(exc)
            raise

    def store_job_credentials(self, job_id: str, credentials: dict, ttl_seconds: int) -> None:
        """Persist reusable encrypted credentials for a job."""
        encrypted = encrypt_json(credentials)
        ttl_epoch = int(time.time() + ttl_seconds)
        ttl_at = datetime.fromtimestamp(ttl_epoch, tz=timezone.utc)
        doc_ref = self._collection.document(_job_doc_id(job_id))
        try:
            doc_ref.set(
                {
                    "kind": "job_credentials",
                    "job_id": job_id,
                    "credentials_enc": encrypted,
                    "enc_v": 1,
                    "ttl_epoch": ttl_epoch,
                    "ttl_at": ttl_at,
                }
            )
        except Exception as exc:
            self._raise_firestore_configuration_error(exc)
            raise

    def load_job_credentials(self, job_id: str) -> Optional[dict]:
        """Load reusable encrypted credentials for a job."""
        doc_ref = self._collection.document(_job_doc_id(job_id))
        try:
            snapshot = doc_ref.get()
        except Exception as exc:
            self._raise_firestore_configuration_error(exc)
            raise
        if not snapshot.exists:
            return None
        item = snapshot.to_dict() or {}
        if item.get("kind") != "job_credentials":
            return None
        if time.time() > int(item.get("ttl_epoch") or 0):
            try:
                doc_ref.delete()
            except Exception:
                pass
            return None
        encrypted = item.get("credentials_enc")
        if not encrypted:
            return None
        return decrypt_json(encrypted)

    def delete_job_credentials(self, job_id: str) -> None:
        """Delete reusable encrypted credentials for a job."""
        doc_ref = self._collection.document(_job_doc_id(job_id))
        try:
            doc_ref.delete()
        except Exception as exc:
            self._raise_firestore_configuration_error(exc)
            raise


def build_credential_store() -> FirestoreCredentialStore:
    """Build credential store."""
    collection = os.getenv("FIRESTORE_CREDENTIALS_COLLECTION") or "skybridge-credentials"
    project_id = resolve_project_id()
    return FirestoreCredentialStore(collection, project_id)


def _job_doc_id(job_id: str) -> str:
    """Build the Firestore document id used for reusable job credentials."""
    return f"job::{job_id}"
