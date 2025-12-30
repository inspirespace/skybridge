from __future__ import annotations

import secrets
import time
from dataclasses import dataclass
from typing import Optional


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
