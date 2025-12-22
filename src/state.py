from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path


@dataclass(frozen=True)
class MigrationRecord:
    flight_id: str
    status: str
    message: str | None
    updated_at: str
    file_hash: str | None
    metadata_hash: str | None


class MigrationState:
    def __init__(self, db_path: Path) -> None:
        self._db_path = db_path
        self._ensure_db()

    def _ensure_db(self) -> None:
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self._db_path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS migrations (
                    flight_id TEXT PRIMARY KEY,
                    status TEXT NOT NULL,
                    message TEXT,
                    updated_at TEXT NOT NULL,
                    file_hash TEXT,
                    metadata_hash TEXT
                )
                """
            )
            self._ensure_column(conn, "file_hash")
            self._ensure_column(conn, "metadata_hash")

    def _ensure_column(self, conn: sqlite3.Connection, column: str) -> None:
        existing = {
            row[1]
            for row in conn.execute("PRAGMA table_info(migrations)").fetchall()
        }
        if column in existing:
            return
        conn.execute(f"ALTER TABLE migrations ADD COLUMN {column} TEXT")

    def get(self, flight_id: str) -> MigrationRecord | None:
        with sqlite3.connect(self._db_path) as conn:
            row = conn.execute(
                """
                SELECT flight_id, status, message, updated_at, file_hash, metadata_hash
                FROM migrations WHERE flight_id = ?
                """,
                (flight_id,),
            ).fetchone()
        if row is None:
            return None
        return MigrationRecord(*row)

    def upsert(
        self,
        flight_id: str,
        status: str,
        message: str | None = None,
        file_hash: str | None = None,
        metadata_hash: str | None = None,
    ) -> None:
        updated_at = datetime.utcnow().isoformat()
        with sqlite3.connect(self._db_path) as conn:
            conn.execute(
                """
                INSERT INTO migrations (flight_id, status, message, updated_at, file_hash, metadata_hash)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(flight_id)
                DO UPDATE SET status = excluded.status, message = excluded.message,
                              updated_at = excluded.updated_at,
                              file_hash = excluded.file_hash,
                              metadata_hash = excluded.metadata_hash
                """,
                (flight_id, status, message, updated_at, file_hash, metadata_hash),
            )
