from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import UUID

from .models import ImportReport, JobRecord, ReviewSummary


@dataclass
class StoredJob:
    job: JobRecord


class JobStore:
    def __init__(self, base_path: Path) -> None:
        self._base_path = base_path
        self._base_path.mkdir(parents=True, exist_ok=True)

    def _job_dir(self, job_id: UUID) -> Path:
        return self._base_path / str(job_id)

    def _job_file(self, job_id: UUID) -> Path:
        return self._job_dir(job_id) / "job.json"

    def _token_file(self, job_id: UUID, purpose: str) -> Path:
        return self._job_dir(job_id) / f"{purpose}.token"

    def list_all_jobs(self) -> list[JobRecord]:
        jobs: list[JobRecord] = []
        for job_dir in self._base_path.iterdir():
            job_file = job_dir / "job.json"
            if not job_file.exists():
                continue
            job_data = json.loads(job_file.read_text())
            jobs.append(JobRecord.model_validate(job_data))
        return sorted(jobs, key=lambda job: job.created_at, reverse=True)

    def job_dir(self, job_id: UUID) -> Path:
        return self._job_dir(job_id)

    def list_jobs(self, user_id: str) -> list[JobRecord]:
        jobs: list[JobRecord] = []
        for job_dir in self._base_path.iterdir():
            job_file = job_dir / "job.json"
            if not job_file.exists():
                continue
            job_data = json.loads(job_file.read_text())
            if job_data.get("user_id") != user_id:
                continue
            jobs.append(JobRecord.model_validate(job_data))
        return sorted(jobs, key=lambda job: job.created_at, reverse=True)

    def load_job(self, job_id: UUID) -> JobRecord:
        job_file = self._job_file(job_id)
        job_data = json.loads(job_file.read_text())
        return JobRecord.model_validate(job_data)

    def save_job(self, job: JobRecord) -> None:
        job_dir = self._job_dir(job.job_id)
        job_dir.mkdir(parents=True, exist_ok=True)
        job_file = job_dir / "job.json"
        job_file.write_text(json.dumps(_serialize(job), indent=2))

    def write_artifact(self, job_id: UUID, name: str, payload: dict[str, Any]) -> None:
        job_dir = self._job_dir(job_id)
        job_dir.mkdir(parents=True, exist_ok=True)
        artifact_file = job_dir / name
        artifact_file.write_text(json.dumps(payload, indent=2))

    def list_artifacts(self, job_id: UUID) -> list[str]:
        job_dir = self._job_dir(job_id)
        if not job_dir.exists():
            return []
        return sorted(
            [item.name for item in job_dir.iterdir() if item.is_file() and item.name != "job.json"]
        )

    def load_artifact(self, job_id: UUID, name: str) -> dict[str, Any]:
        artifact_file = self._job_dir(job_id) / name
        return json.loads(artifact_file.read_text())

    def write_token(self, job_id: UUID, purpose: str, token: str) -> None:
        token_file = self._token_file(job_id, purpose)
        token_file.write_text(token)

    def read_token(self, job_id: UUID, purpose: str) -> str | None:
        token_file = self._token_file(job_id, purpose)
        if not token_file.exists():
            return None
        return token_file.read_text().strip()

    def clear_token(self, job_id: UUID, purpose: str) -> None:
        token_file = self._token_file(job_id, purpose)
        if token_file.exists():
            token_file.unlink()


def _serialize(job: JobRecord) -> dict[str, Any]:
    def _normalize(value: Any) -> Any:
        if isinstance(value, datetime):
            return value.isoformat()
        if isinstance(value, UUID):
            return str(value)
        if isinstance(value, ReviewSummary):
            return json.loads(value.model_dump_json())
        if isinstance(value, ImportReport):
            return json.loads(value.model_dump_json())
        return value

    raw = job.model_dump()
    return {key: _normalize(value) for key, value in raw.items()}
