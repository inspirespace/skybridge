from __future__ import annotations

"""Short-lived credential store for worker jobs.

Credentials are issued with a TTL and can be claimed once by the worker.
Backed by in-memory dict (dev) or DynamoDB (prod).
"""

import secrets
import time
import os
import json
from dataclasses import dataclass
from typing import Optional

import boto3


@dataclass
class _Entry:
    job_id: str
    purpose: str
    credentials: dict
    expires_at: float
    used: bool = False


class CredentialStore:
    def __init__(self) -> None:
        self._entries: dict[str, _Entry] = {}

    def issue(self, job_id: str, purpose: str, credentials: dict, ttl_seconds: int) -> str:
        token = secrets.token_urlsafe(32)
        self._entries[token] = _Entry(
            job_id=job_id,
            purpose=purpose,
            credentials=credentials,
            expires_at=time.time() + ttl_seconds,
        )
        return token

    def claim(self, token: str, job_id: str, purpose: str) -> Optional[dict]:
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


class DynamoCredentialStore:
    def __init__(self, table_name: str) -> None:
        self._table = boto3.resource("dynamodb").Table(table_name)

    def issue(self, job_id: str, purpose: str, credentials: dict, ttl_seconds: int) -> str:
        token = secrets.token_urlsafe(32)
        ttl_epoch = int(time.time() + ttl_seconds)
        self._table.put_item(
            Item={
                "token": token,
                "job_id": job_id,
                "purpose": purpose,
                "credentials": json.dumps(credentials),
                "ttl_epoch": ttl_epoch,
                "used": False,
            }
        )
        return token

    def claim(self, token: str, job_id: str, purpose: str) -> Optional[dict]:
        response = self._table.get_item(Key={"token": token})
        item = response.get("Item") if isinstance(response, dict) else None
        if not item:
            return None
        if item.get("used") or item.get("job_id") != job_id or item.get("purpose") != purpose:
            return None
        if time.time() > int(item.get("ttl_epoch") or 0):
            self._table.delete_item(Key={"token": token})
            return None
        self._table.delete_item(Key={"token": token})
        try:
            return json.loads(item.get("credentials") or "{}")
        except json.JSONDecodeError:
            return None


def build_credential_store() -> CredentialStore | DynamoCredentialStore:
    if (os.getenv("BACKEND_DYNAMO_ENABLED") or "false").lower() in {"1", "true", "yes", "on"}:
        table_name = os.getenv("DYNAMO_CREDENTIALS_TABLE") or ""
        if not table_name:
            raise RuntimeError("DYNAMO_CREDENTIALS_TABLE is required when BACKEND_DYNAMO_ENABLED=1")
        return DynamoCredentialStore(table_name)
    return CredentialStore()
