"""Persistence layer for job metadata and artifacts.

Supports:
- Local filesystem storage (dev)
- Firestore for job metadata (GCP)
- GCS via ObjectStore for artifacts (GCP)
"""
from __future__ import annotations

import json
import logging
import os
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from shutil import rmtree
from typing import Any, Callable
from uuid import UUID

from .firebase_errors import raise_if_missing_firestore_database
from .models import FlightSummary, ImportReport, JobRecord, ReviewSummary
from .object_store import ObjectStoreProtocol


@dataclass
class StoredJob:
    job: JobRecord


class JobStore:
    """Store job metadata and artifacts across local and cloud backends."""
    def __init__(
        self,
        base_path: Path,
        object_store: ObjectStoreProtocol | None = None,
        firestore_collection: str | None = None,
        firestore_project: str | None = None,
    ) -> None:
        """Internal helper for init  ."""
        self._base_path = base_path
        self._object_store = object_store
        self._firestore = None
        self._firestore_collection = None
        self._firestore_project = firestore_project
        self._firestore_database = "(default)"
        self._token_cache: dict[tuple[str, str], str] = {}
        if firestore_collection:
            from google.cloud import firestore

            self._firestore = firestore.Client(project=firestore_project or None)
            self._firestore_collection = self._firestore.collection(firestore_collection)
        self._base_path.mkdir(parents=True, exist_ok=True)

    def _raise_firestore_configuration_error(self, exc: Exception) -> None:
        """Translate Firestore database lookup failures to config errors."""
        raise_if_missing_firestore_database(
            exc,
            project_id=self._firestore_project,
            database_id=self._firestore_database,
        )

    def _job_dir(self, job_id: UUID) -> Path:
        """Internal helper for job dir."""
        return self._base_path / str(job_id)

    @property
    def object_store(self) -> ObjectStoreProtocol | None:
        """Handle object store."""
        return self._object_store

    def _object_prefix_for_job(self, job_id: UUID, *, user_id: str | None = None) -> str:
        """Internal helper for object prefix for job."""
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
        """Internal helper for job file."""
        return self._job_dir(job_id) / "job.json"

    def list_all_jobs(self) -> list[JobRecord]:
        """Handle list all jobs."""
        self.cleanup_expired()
        if self._firestore_collection:
            jobs: list[JobRecord] = []
            try:
                for doc in self._firestore_collection.stream():
                    payload = doc.to_dict() or {}
                    job_payload = payload.get("payload")
                    if isinstance(job_payload, str):
                        job_payload = json.loads(job_payload)
                    if not isinstance(job_payload, dict):
                        continue
                    job = JobRecord.model_validate(job_payload)
                    job = self._maybe_enrich_review_summary(job)
                    if self._is_expired(job):
                        self.delete_job(job.job_id)
                        continue
                    jobs.append(job)
            except Exception as exc:
                self._raise_firestore_configuration_error(exc)
                raise
            return sorted(jobs, key=lambda job: job.created_at, reverse=True)

        jobs = []
        for job_dir in self._base_path.iterdir():
            job_file = job_dir / "job.json"
            if not job_file.exists():
                continue
            job_data = json.loads(job_file.read_text())
            job = JobRecord.model_validate(job_data)
            job = self._maybe_enrich_review_summary(job)
            if self._is_expired(job):
                self.delete_job(job.job_id)
                continue
            jobs.append(job)
        return sorted(jobs, key=lambda job: job.created_at, reverse=True)

    def job_dir(self, job_id: UUID) -> Path:
        """Handle job dir."""
        return self._job_dir(job_id)

    def list_jobs(self, user_id: str) -> list[JobRecord]:
        """Handle list jobs."""
        self.cleanup_expired()
        if self._firestore_collection:
            jobs: list[JobRecord] = []
            query = self._firestore_collection.where("user_id", "==", user_id)
            try:
                for doc in query.stream():
                    payload = doc.to_dict() or {}
                    job_payload = payload.get("payload")
                    if isinstance(job_payload, str):
                        job_payload = json.loads(job_payload)
                    if not isinstance(job_payload, dict):
                        continue
                    job = JobRecord.model_validate(job_payload)
                    job = self._maybe_enrich_review_summary(job)
                    if self._is_expired(job):
                        self.delete_job(job.job_id)
                        continue
                    jobs.append(job)
            except Exception as exc:
                self._raise_firestore_configuration_error(exc)
                raise
            return sorted(jobs, key=lambda job: job.created_at, reverse=True)

        jobs = []
        for job_dir in self._base_path.iterdir():
            job_file = job_dir / "job.json"
            if not job_file.exists():
                continue
            job_data = json.loads(job_file.read_text())
            if job_data.get("user_id") != user_id:
                continue
            job = JobRecord.model_validate(job_data)
            job = self._maybe_enrich_review_summary(job)
            if self._is_expired(job):
                self.delete_job(job.job_id)
                continue
            jobs.append(job)
        return sorted(jobs, key=lambda job: job.created_at, reverse=True)

    def delete_jobs_for_user(self, user_id: str) -> None:
        """Delete jobs for user."""
        jobs = self.list_jobs(user_id)
        for job in jobs:
            try:
                self.delete_job(job.job_id, user_id=user_id)
            except FileNotFoundError:
                continue

    def load_job(self, job_id: UUID) -> JobRecord:
        """Handle load job."""
        if self._firestore_collection:
            try:
                doc = self._firestore_collection.document(str(job_id)).get()
            except Exception as exc:
                self._raise_firestore_configuration_error(exc)
                raise
            if not doc.exists:
                raise FileNotFoundError("Job not found")
            payload = doc.to_dict() or {}
            job_payload = payload.get("payload")
            if isinstance(job_payload, str):
                job_payload = json.loads(job_payload)
            if not isinstance(job_payload, dict):
                raise FileNotFoundError("Job not found")
            job = JobRecord.model_validate(job_payload)
            if self._is_expired(job):
                self.delete_job(job.job_id)
                raise FileNotFoundError("Job expired")
            return self._maybe_enrich_review_summary(job)

        job_file = self._job_file(job_id)
        if not job_file.exists():
            raise FileNotFoundError("Job not found")
        job_data = json.loads(job_file.read_text())
        job = JobRecord.model_validate(job_data)
        if self._is_expired(job):
            self.delete_job(job.job_id)
            raise FileNotFoundError("Job expired")
        return self._maybe_enrich_review_summary(job)

    def delete_job(self, job_id: UUID, *, user_id: str | None = None) -> None:
        """Delete job."""
        _delete_related_credentials(job_id)
        if self._firestore_collection:
            try:
                doc_ref = self._firestore_collection.document(str(job_id))
                doc = doc_ref.get()
                if doc.exists:
                    payload = doc.to_dict() or {}
                    raw_user_id = payload.get("user_id")
                    if user_id is None and isinstance(raw_user_id, str):
                        user_id = raw_user_id
                try:
                    doc_ref.delete()
                except Exception as exc:
                    self._raise_firestore_configuration_error(exc)
                    raise
            except FileNotFoundError:
                pass
        job_dir = self._job_dir(job_id)
        if job_dir.exists():
            rmtree(job_dir)
        if self._object_store and _bool_env("BACKEND_OBJECT_STORE_DELETE_ON_CLEAR", False):
            prefix = self._object_prefix_for_job(job_id, user_id=user_id)
            if prefix:
                try:
                    self._object_store.delete_prefix(prefix)
                except Exception as exc:
                    logging.getLogger(__name__).warning(
                        "Failed to delete remote artifacts for job %s: %s", job_id, exc
                    )

    def save_job(self, job: JobRecord) -> None:
        """Handle save job."""
        job_dir = self._job_dir(job.job_id)
        job_dir.mkdir(parents=True, exist_ok=True)
        job_file = job_dir / "job.json"
        job_file.write_text(json.dumps(_serialize(job), indent=2))
        if self._firestore_collection:
            ttl_epoch = _ttl_epoch(job.created_at)
            ttl_at = datetime.fromtimestamp(ttl_epoch, tz=timezone.utc)
            item = {
                "user_id": job.user_id,
                "job_id": str(job.job_id),
                "payload": _serialize(job),
                "created_at": job.created_at,
                "updated_at": job.updated_at,
                "ttl_epoch": ttl_epoch,
                "ttl_at": ttl_at,
            }
            try:
                self._firestore_collection.document(str(job.job_id)).set(item)
            except Exception as exc:
                self._raise_firestore_configuration_error(exc)
                raise

    def write_artifact(self, job_id: UUID, name: str, payload: dict[str, Any]) -> None:
        """Handle write artifact."""
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
        """Handle upload artifact."""
        if not self._object_store or not path.exists():
            return
        key = self._object_store.key_for(self.load_job(job_id).user_id, str(job_id), name)
        try:
            self._object_store.put_file(key, path)
        except Exception as exc:
            logging.getLogger(__name__).warning(
                "Failed to upload artifact file %s for job %s: %s", name, job_id, exc
            )

    def upload_artifact_as(self, job_id: UUID, artifact_name: str, path: Path) -> None:
        """Upload a local file under an explicit artifact name."""
        if not self._object_store or not path.exists():
            return
        key = self._object_store.key_for(
            self.load_job(job_id).user_id,
            str(job_id),
            artifact_name,
        )
        try:
            self._object_store.put_file(key, path)
        except Exception as exc:
            logging.getLogger(__name__).warning(
                "Failed to upload artifact file %s for job %s: %s", artifact_name, job_id, exc
            )

    def upload_artifact_dir(
        self,
        job_id: UUID,
        *,
        prefix: str,
        directory: Path,
        suffix: str | None = None,
    ) -> None:
        """Handle upload artifact dir."""
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

    def materialize_artifact_file(self, job_id: UUID, name: str, target_path: Path) -> bool:
        """Restore a file artifact from object storage onto local disk when needed."""
        if self._object_store:
            key = self._object_store.key_for(self.load_job(job_id).user_id, str(job_id), name)
            payload = self._object_store.get_bytes(key)
            if payload is not None:
                target_path.parent.mkdir(parents=True, exist_ok=True)
                target_path.write_bytes(payload)
                return True
        return target_path.exists()

    def list_artifacts(self, job_id: UUID) -> list[str]:
        """Handle list artifacts."""
        job_dir = self._job_dir(job_id)
        artifacts: set[str] = set()
        if job_dir.exists():
            artifacts.update(
                item.name for item in job_dir.iterdir() if item.is_file() and item.name != "job.json"
            )
        if self._object_store:
            prefix = self._object_prefix_for_job(job_id)
            if prefix:
                artifacts.update(self._object_store.list_prefix(prefix))
        return sorted(artifacts)

    def load_artifact(self, job_id: UUID, name: str) -> dict[str, Any]:
        """Handle load artifact."""
        artifact_file = self._job_dir(job_id) / name
        if self._object_store:
            key = self._object_store.key_for(self.load_job(job_id).user_id, str(job_id), name)
            try:
                payload = self._object_store.get_json(key)
            except Exception as exc:
                logging.getLogger(__name__).warning(
                    "Failed to read remote artifact %s for job %s: %s",
                    name,
                    job_id,
                    exc,
                )
            else:
                if payload is not None:
                    artifact_file.parent.mkdir(parents=True, exist_ok=True)
                    artifact_file.write_text(json.dumps(payload, indent=2))
                    return payload
        if artifact_file.exists():
            return json.loads(artifact_file.read_text())
        raise FileNotFoundError("Artifact not found")

    def write_token(self, job_id: UUID, purpose: str, token: str) -> None:
        """Handle write token."""
        self._token_cache[(str(job_id), purpose)] = token

    def read_token(self, job_id: UUID, purpose: str) -> str | None:
        """Handle read token."""
        return self._token_cache.get((str(job_id), purpose))

    def _maybe_enrich_review_summary(self, job: JobRecord) -> JobRecord:
        """Backfill origin/destination from review payload when missing."""
        review_summary = job.review_summary
        if not review_summary or not review_summary.flights:
            return job
        if all(flight.origin and flight.destination for flight in review_summary.flights):
            return job
        payload = self._load_review_payload(job)
        if not payload:
            return job
        mapping = _extract_locations(
            payload,
            raw_loader=lambda raw_path: self._load_raw_payload(job, raw_path),
        )
        if not mapping:
            return job
        updated = False
        updated_flights: list[FlightSummary] = []
        for flight in review_summary.flights:
            origin = flight.origin
            destination = flight.destination
            mapped = mapping.get(flight.flight_id)
            if mapped:
                origin = origin or mapped[0]
                destination = destination or mapped[1]
            if origin != flight.origin or destination != flight.destination:
                updated = True
            updated_flights.append(
                flight.model_copy(update={"origin": origin, "destination": destination})
            )
        if not updated:
            return job
        job.review_summary = review_summary.model_copy(update={"flights": updated_flights})
        self.save_job(job)
        return job

    def _load_review_payload(self, job: JobRecord) -> dict[str, Any] | None:
        """Load review payload for enrichment."""
        job_dir = self._job_dir(job.job_id)
        review_path = job_dir / "review.json"
        if not self._object_store:
            return json.loads(review_path.read_text()) if review_path.exists() else None
        key = self._object_store.key_for(job.user_id, str(job.job_id), "review.json")
        payload = self._object_store.get_json(key)
        if payload is not None:
            review_path.parent.mkdir(parents=True, exist_ok=True)
            review_path.write_text(json.dumps(payload, indent=2))
            return payload
        if review_path.exists():
            return json.loads(review_path.read_text())
        return None

    def _load_raw_payload(self, job: JobRecord, raw_path: str) -> dict[str, Any] | None:
        """Load raw CloudAhoy payload for enrichment."""
        raw_file = Path(raw_path)
        filename = raw_file.name
        job_dir = self._job_dir(job.job_id) / "cloudahoy_exports" / filename
        if self._object_store:
            key = self._object_store.key_for(job.user_id, str(job.job_id), f"cloudahoy_exports/{filename}")
            payload = self._object_store.get_json(key)
            if payload is not None:
                job_dir.parent.mkdir(parents=True, exist_ok=True)
                job_dir.write_text(json.dumps(payload, indent=2))
                return payload
        for candidate in (raw_file, job_dir):
            if candidate.exists():
                try:
                    return json.loads(candidate.read_text())
                except json.JSONDecodeError:
                    return None
        return None

    def clear_token(self, job_id: UUID, purpose: str) -> None:
        """Handle clear token."""
        self._token_cache.pop((str(job_id), purpose), None)

    def cleanup_expired(self) -> int:
        """Remove expired jobs from storage. Returns count deleted."""
        deleted = 0
        now = int(datetime.now(timezone.utc).timestamp())
        if self._firestore_collection:
            query = self._firestore_collection.where("ttl_epoch", "<", now)
            try:
                for doc in query.stream():
                    payload = doc.to_dict() or {}
                    user_id = payload.get("user_id")
                    try:
                        job_id = UUID(doc.id)
                    except ValueError:
                        doc.reference.delete()
                        deleted += 1
                        continue
                    self.delete_job(job_id, user_id=user_id if isinstance(user_id, str) else None)
                    deleted += 1
            except Exception as exc:
                self._raise_firestore_configuration_error(exc)
                raise
            return deleted
        for job_dir in self._base_path.iterdir():
            if not job_dir.is_dir():
                continue
            job_file = job_dir / "job.json"
            if not job_file.exists():
                continue
            try:
                job_data = json.loads(job_file.read_text())
                job = JobRecord.model_validate(job_data)
            except Exception:
                continue
            if self._is_expired(job):
                try:
                    self.delete_job(job.job_id, user_id=job.user_id)
                except Exception:
                    pass
                deleted += 1
        return deleted

    def _is_expired(self, job: JobRecord) -> bool:
        """Internal helper for is expired."""
        retention_days = int(os.getenv("BACKEND_RETENTION_DAYS") or "7")
        if retention_days <= 0:
            return False
        now = datetime.now(timezone.utc)
        created_at = job.created_at
        if created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=timezone.utc)
        return created_at < now - timedelta(days=retention_days)


def _ttl_epoch(created_at: datetime) -> int:
    """Internal helper for ttl epoch."""
    retention_days = int(os.getenv("BACKEND_RETENTION_DAYS") or "7")
    if retention_days <= 0:
        retention_days = 7
    if created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=timezone.utc)
    return int(created_at.timestamp() + retention_days * 86400)


def _extract_locations(
    payload: dict[str, Any],
    *,
    raw_loader: Callable[[str], dict[str, Any] | None] | None = None,
) -> dict[str, tuple[str | None, str | None]]:
    """Extract origin/destination values from review payload."""
    items = payload.get("items", [])
    if not isinstance(items, list):
        return {}
    mapping: dict[str, tuple[str | None, str | None]] = {}
    for item in items:
        if not isinstance(item, dict):
            continue
        flight_id = item.get("flight_id")
        if not isinstance(flight_id, str) or not flight_id:
            continue
        metadata = item.get("metadata")
        if not isinstance(metadata, dict):
            metadata = {}
        origin = _coerce_location(
            metadata.get("origin")
            or metadata.get("aircraft_from")
            or metadata.get("event_from")
            or metadata.get("from")
        )
        destination = _coerce_location(
            metadata.get("destination")
            or metadata.get("aircraft_to")
            or metadata.get("event_to")
            or metadata.get("to")
        )
        if (origin is None or destination is None) and raw_loader:
            raw_path = item.get("raw_path")
            if isinstance(raw_path, str) and raw_path:
                raw_payload = raw_loader(raw_path)
                if isinstance(raw_payload, dict):
                    raw_meta = _extract_metadata_from_raw(raw_payload)
                    origin = origin or _coerce_location(
                        raw_meta.get("origin")
                        or raw_meta.get("aircraft_from")
                        or raw_meta.get("event_from")
                        or raw_meta.get("from")
                    )
                    destination = destination or _coerce_location(
                        raw_meta.get("destination")
                        or raw_meta.get("aircraft_to")
                        or raw_meta.get("event_to")
                        or raw_meta.get("to")
                    )
        if origin or destination:
            mapping[flight_id] = (origin, destination)
    return mapping


def _coerce_location(value: Any) -> str | None:
    """Coerce location values to strings."""
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        code = value.get("c")
        name = value.get("t")
        if isinstance(code, str) and code:
            return code
        if isinstance(name, str) and name:
            return name
    return None


def _extract_metadata_from_raw(raw_payload: dict[str, Any]) -> dict[str, Any]:
    """Extract metadata from raw CloudAhoy payload."""
    flt = raw_payload.get("flt")
    if not isinstance(flt, dict):
        return {}
    meta = flt.get("Meta")
    if not isinstance(meta, dict):
        return {}
    fields = {
        "aircraft_from": meta.get("from"),
        "aircraft_to": meta.get("to"),
        "event_from": meta.get("e_from"),
        "event_to": meta.get("e_to"),
        "origin": meta.get("origin"),
        "destination": meta.get("destination"),
    }
    return {key: value for key, value in fields.items() if value not in (None, "", [])}


def _serialize(job: JobRecord) -> dict[str, Any]:
    """Internal helper for serialize."""
    def _normalize(value: Any) -> Any:
        """Internal helper for normalize."""
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
    """Internal helper for bool env."""
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _delete_related_credentials(job_id: UUID) -> None:
    """Best-effort credential cleanup for explicit and retention-based job deletion."""
    if not os.getenv("BACKEND_ENCRYPTION_KEY"):
        return
    try:
        from .credential_store import build_credential_store

        store = build_credential_store()
        if hasattr(store, "delete_all_for_job"):
            store.delete_all_for_job(str(job_id))
        elif hasattr(store, "delete_job_credentials"):
            store.delete_job_credentials(str(job_id))
    except Exception as exc:
        logging.getLogger(__name__).warning(
            "Failed to delete credentials for job %s: %s",
            job_id,
            exc,
        )
