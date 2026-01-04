from __future__ import annotations

"""Persistence layer for job metadata and artifacts.

Supports:
- Local filesystem storage (dev)
- DynamoDB for job metadata (prod)
- S3 via ObjectStore for artifacts (prod)
"""

import json
import logging
import os
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from shutil import rmtree
from typing import Any
from uuid import UUID

import boto3
from boto3.dynamodb.conditions import Key

from .models import ImportReport, JobRecord, ReviewSummary
from .object_store import ObjectStore


@dataclass
class StoredJob:
    job: JobRecord


class JobStore:
    """Store job metadata and artifacts across local and cloud backends."""
    def __init__(
        self,
        base_path: Path,
        object_store: ObjectStore | None = None,
        dynamo_table_name: str | None = None,
    ) -> None:
        self._base_path = base_path
        self._object_store = object_store
        self._dynamo_table = (
            boto3.resource("dynamodb").Table(dynamo_table_name)
            if dynamo_table_name
            else None
        )
        self._base_path.mkdir(parents=True, exist_ok=True)

    def _job_dir(self, job_id: UUID) -> Path:
        return self._base_path / str(job_id)

    @property
    def object_store(self) -> ObjectStore | None:
        return self._object_store

    def _object_prefix_for_job(self, job_id: UUID, *, user_id: str | None = None) -> str:
        if not self._object_store:
            return ""
        if user_id is None:
            try:
                job = self.load_job(job_id)
                user_id = job.user_id
            except FileNotFoundError:
                return ""
        return self._object_store.key_for(user_id, str(job_id))

    def _job_file(self, job_id: UUID) -> Path:
        return self._job_dir(job_id) / "job.json"

    def _token_file(self, job_id: UUID, purpose: str) -> Path:
        return self._job_dir(job_id) / f"{purpose}.token"

    def list_all_jobs(self) -> list[JobRecord]:
        if self._dynamo_table:
            jobs: list[JobRecord] = []
            response = self._dynamo_table.scan()
            for item in response.get("Items", []):
                job = _deserialize_item(item)
                if self._is_expired(job):
                    self.delete_job(job.job_id)
                    continue
                jobs.append(job)
            return sorted(jobs, key=lambda job: job.created_at, reverse=True)

        jobs: list[JobRecord] = []
        for job_dir in self._base_path.iterdir():
            job_file = job_dir / "job.json"
            if not job_file.exists():
                continue
            job_data = json.loads(job_file.read_text())
            job = JobRecord.model_validate(job_data)
            if self._is_expired(job):
                self.delete_job(job.job_id)
                continue
            jobs.append(job)
        return sorted(jobs, key=lambda job: job.created_at, reverse=True)

    def job_dir(self, job_id: UUID) -> Path:
        return self._job_dir(job_id)

    def list_jobs(self, user_id: str) -> list[JobRecord]:
        if self._dynamo_table:
            response = self._dynamo_table.query(
                KeyConditionExpression=Key("user_id").eq(user_id)
            )
            jobs: list[JobRecord] = []
            for item in response.get("Items", []):
                job = _deserialize_item(item)
                if self._is_expired(job):
                    self.delete_job(job.job_id)
                    continue
                jobs.append(job)
            return sorted(jobs, key=lambda job: job.created_at, reverse=True)

        jobs: list[JobRecord] = []
        for job_dir in self._base_path.iterdir():
            job_file = job_dir / "job.json"
            if not job_file.exists():
                continue
            job_data = json.loads(job_file.read_text())
            if job_data.get("user_id") != user_id:
                continue
            job = JobRecord.model_validate(job_data)
            if self._is_expired(job):
                self.delete_job(job.job_id)
                continue
            jobs.append(job)
        return sorted(jobs, key=lambda job: job.created_at, reverse=True)

    def delete_jobs_for_user(self, user_id: str) -> None:
        jobs = self.list_jobs(user_id)
        for job in jobs:
            try:
                self.delete_job(job.job_id, user_id=user_id)
            except FileNotFoundError:
                continue

    def load_job(self, job_id: UUID) -> JobRecord:
        if self._dynamo_table:
            response = self._dynamo_table.query(
                IndexName="job_id-index",
                KeyConditionExpression=Key("job_id").eq(str(job_id)),
            )
            items = response.get("Items", [])
            if not items:
                raise FileNotFoundError("Job not found")
            job = _deserialize_item(items[0])
            if self._is_expired(job):
                self.delete_job(job.job_id)
                raise FileNotFoundError("Job expired")
            return job

        job_file = self._job_file(job_id)
        job_data = json.loads(job_file.read_text())
        job = JobRecord.model_validate(job_data)
        if self._is_expired(job):
            self.delete_job(job.job_id)
            raise FileNotFoundError("Job expired")
        return job

    def delete_job(self, job_id: UUID, *, user_id: str | None = None) -> None:
        if self._dynamo_table:
            try:
                job = self.load_job(job_id)
                self._dynamo_table.delete_item(
                    Key={"user_id": job.user_id, "job_id": str(job.job_id)}
                )
                user_id = user_id or job.user_id
            except FileNotFoundError:
                pass
        job_dir = self._job_dir(job_id)
        if job_dir.exists():
            rmtree(job_dir)
        if self._object_store and _bool_env("BACKEND_S3_DELETE_ON_CLEAR", False):
            prefix = self._object_prefix_for_job(job_id, user_id=user_id)
            if prefix:
                try:
                    self._object_store.delete_prefix(prefix)
                except Exception as exc:
                    logging.getLogger(__name__).warning(
                        "Failed to delete remote artifacts for job %s: %s", job_id, exc
                    )

    def save_job(self, job: JobRecord) -> None:
        job_dir = self._job_dir(job.job_id)
        job_dir.mkdir(parents=True, exist_ok=True)
        job_file = job_dir / "job.json"
        job_file.write_text(json.dumps(_serialize(job), indent=2))
        if self._dynamo_table:
            ttl_epoch = _ttl_epoch(job.created_at)
            item = {
                "user_id": job.user_id,
                "job_id": str(job.job_id),
                "payload": json.dumps(_serialize(job)),
                "created_at": job.created_at.isoformat(),
                "updated_at": job.updated_at.isoformat(),
                "ttl_epoch": ttl_epoch,
            }
            self._dynamo_table.put_item(Item=item)

    def write_artifact(self, job_id: UUID, name: str, payload: dict[str, Any]) -> None:
        job_dir = self._job_dir(job_id)
        job_dir.mkdir(parents=True, exist_ok=True)
        artifact_file = job_dir / name
        artifact_file.write_text(json.dumps(payload, indent=2))
        if self._object_store:
            key = self._object_store.key_for(self.load_job(job_id).user_id, str(job_id), name)
            try:
                self._object_store.put_json(key, payload)
            except Exception as exc:
                logging.getLogger(__name__).warning(
                    "Failed to upload artifact %s for job %s: %s", name, job_id, exc
                )

    def upload_artifact(self, job_id: UUID, name: str, path: Path) -> None:
        if not self._object_store or not path.exists():
            return
        key = self._object_store.key_for(self.load_job(job_id).user_id, str(job_id), name)
        try:
            self._object_store.put_file(key, path)
        except Exception as exc:
            logging.getLogger(__name__).warning(
                "Failed to upload artifact file %s for job %s: %s", name, job_id, exc
            )

    def upload_artifact_dir(
        self,
        job_id: UUID,
        *,
        prefix: str,
        directory: Path,
        suffix: str | None = None,
    ) -> None:
        if not self._object_store or not directory.exists():
            return
        user_id = self.load_job(job_id).user_id
        for path in directory.rglob("*"):
            if not path.is_file():
                continue
            if suffix and not path.name.endswith(suffix):
                continue
            name = f"{prefix}/{path.relative_to(directory)}"
            key = self._object_store.key_for(user_id, str(job_id), name)
            try:
                self._object_store.put_file(key, path)
            except Exception as exc:
                logging.getLogger(__name__).warning(
                    "Failed to upload artifact file %s for job %s: %s", name, job_id, exc
                )

    def list_artifacts(self, job_id: UUID) -> list[str]:
        job_dir = self._job_dir(job_id)
        if not job_dir.exists() and self._object_store:
            prefix = self._object_prefix_for_job(job_id)
            return self._object_store.list_prefix(prefix)
        if not job_dir.exists():
            return []
        return sorted(
            [item.name for item in job_dir.iterdir() if item.is_file() and item.name != "job.json"]
        )

    def load_artifact(self, job_id: UUID, name: str) -> dict[str, Any]:
        artifact_file = self._job_dir(job_id) / name
        if artifact_file.exists():
            return json.loads(artifact_file.read_text())
        if self._object_store:
            key = self._object_store.key_for(self.load_job(job_id).user_id, str(job_id), name)
            payload = self._object_store.get_json(key)
            if payload is not None:
                return payload
        raise FileNotFoundError("Artifact not found")

    def write_token(self, job_id: UUID, purpose: str, token: str) -> None:
        token_file = self._token_file(job_id, purpose)
        token_file.write_text(token)
        if self._dynamo_table:
            job = self.load_job(job_id)
            field = f"{purpose}_token"
            self._dynamo_table.update_item(
                Key={"user_id": job.user_id, "job_id": str(job.job_id)},
                UpdateExpression=f"SET {field} = :token",
                ExpressionAttributeValues={":token": token},
            )

    def read_token(self, job_id: UUID, purpose: str) -> str | None:
        token_file = self._token_file(job_id, purpose)
        if not token_file.exists():
            if self._dynamo_table:
                try:
                    job = self.load_job(job_id)
                except FileNotFoundError:
                    return None
                field = f"{purpose}_token"
                response = self._dynamo_table.get_item(
                    Key={"user_id": job.user_id, "job_id": str(job.job_id)},
                    ProjectionExpression=field,
                )
                item = response.get("Item") if isinstance(response, dict) else None
                return item.get(field) if item else None
            return None
        return token_file.read_text().strip()

    def clear_token(self, job_id: UUID, purpose: str) -> None:
        token_file = self._token_file(job_id, purpose)
        if token_file.exists():
            token_file.unlink()
        if self._dynamo_table:
            try:
                job = self.load_job(job_id)
            except FileNotFoundError:
                return
            field = f"{purpose}_token"
            self._dynamo_table.update_item(
                Key={"user_id": job.user_id, "job_id": str(job.job_id)},
                UpdateExpression=f"REMOVE {field}",
            )

    def _is_expired(self, job: JobRecord) -> bool:
        retention_days = int(os.getenv("BACKEND_RETENTION_DAYS") or "7")
        if retention_days <= 0:
            return False
        now = datetime.now(timezone.utc)
        created_at = job.created_at
        if created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=timezone.utc)
        return created_at < now - timedelta(days=retention_days)


def _ttl_epoch(created_at: datetime) -> int:
    retention_days = int(os.getenv("BACKEND_RETENTION_DAYS") or "7")
    if retention_days <= 0:
        retention_days = 7
    if created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=timezone.utc)
    return int(created_at.timestamp() + retention_days * 86400)


def _deserialize_item(item: dict[str, Any]) -> JobRecord:
    payload = item.get("payload") or "{}"
    data = json.loads(payload)
    return JobRecord.model_validate(data)


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
        if isinstance(value, list):
            return [_normalize(item) for item in value]
        if isinstance(value, dict):
            return {key: _normalize(item) for key, item in value.items()}
        return value

    raw = job.model_dump()
    return {key: _normalize(value) for key, value in raw.items()}


def _bool_env(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}
