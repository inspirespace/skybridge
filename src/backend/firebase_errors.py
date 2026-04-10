"""Helpers for normalizing Firebase/Firestore configuration failures."""
from __future__ import annotations


class FirestoreDatabaseNotConfiguredError(RuntimeError):
    """Raised when the configured Cloud Firestore database is missing."""

    def __init__(self, project_id: str | None, database_id: str = "(default)") -> None:
        self.project_id = project_id
        self.database_id = database_id
        project_label = project_id or "the active Firebase project"
        super().__init__(
            f"Cloud Firestore database {database_id} is not configured for project {project_label}."
        )


def raise_if_missing_firestore_database(
    exc: Exception,
    *,
    project_id: str | None,
    database_id: str = "(default)",
) -> None:
    """Re-raise Firestore 404 database errors as configuration failures."""

    message = str(exc).lower()
    if exc.__class__.__name__ == "NotFound" and "database" in message and "does not exist" in message:
        raise FirestoreDatabaseNotConfiguredError(project_id, database_id) from exc
