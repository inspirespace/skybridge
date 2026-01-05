import sqlite3
import tempfile
import unittest
from pathlib import Path

from src.core.state import MigrationState


class MigrationStateTests(unittest.TestCase):
    def test_upsert_and_get(self) -> None:
    """Test upsert and get."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "state.db"
            state = MigrationState(db_path)

            state.upsert("flight-1", "ok", None)
            record = state.get("flight-1")

            self.assertIsNotNone(record)
            assert record is not None
            self.assertEqual(record.flight_id, "flight-1")
            self.assertEqual(record.status, "ok")

    def test_database_created(self) -> None:
    """Test database created."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "state.db"
            MigrationState(db_path)

            with sqlite3.connect(db_path) as conn:
                rows = conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name='migrations'"
                ).fetchall()

            self.assertEqual(len(rows), 1)
