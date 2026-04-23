"""tests/test_migration_reconcile.py module."""
from __future__ import annotations

import json
from pathlib import Path

from src.core.migration import (
    reconcile_aircraft_from_report,
    reconcile_crew_from_report,
    reconcile_metadata_from_report,
)


class DummyFlySto:
    def __init__(self) -> None:
        """Internal helper for init  ."""
        self.assigned: list[str] = []
        self.fetch_calls = 0

    def resolve_log_for_file(self, filename: str, **_kwargs):
        """Handle resolve log for file."""
        return "log-new", None, None

    def assign_crew_for_log_id(self, log_id: str | None, crew):
        """Handle assign crew for log id."""
        if log_id:
            self.assigned.append(log_id)

    def assign_crew_for_log_ids(self, log_ids, crew):
        """Batched crew assignment — mirrors the real client's helper."""
        for log_id in log_ids:
            if log_id:
                self.assigned.append(log_id)

    def fetch_log_metadata(self, log_id: str):
        """Handle fetch log metadata."""
        self.fetch_calls += 1
        if self.fetch_calls == 1:
            return {"items": [{"id": log_id, "annotations": {}}]}
        return {"items": [{"id": log_id, "annotations": {"crew": [[1, -6]]}}]}


def test_reconcile_crew_resolves_and_retries(monkeypatch, tmp_path: Path):
    """Test reconcile crew resolves and retries."""
    report_path = tmp_path / "import_report.json"
    payload = {
        "items": [
            {
                "flight_id": "flight-1",
                "flysto_log_id": "log-old",
                "file_path": str(tmp_path / "flight.g3x.csv"),
                "crew": [{"name": "Alex", "role": "Student", "is_pic": False}],
            }
        ]
    }
    report_path.write_text(json.dumps(payload))

    dummy = DummyFlySto()
    monkeypatch.setattr("src.core.migration.time.sleep", lambda _seconds: None)

    updated = reconcile_crew_from_report(report_path, dummy)

    assert updated == 1
    assert dummy.assigned == ["log-new", "log-new"]
    updated_payload = json.loads(report_path.read_text())
    assert updated_payload["items"][0]["flysto_log_id"] == "log-new"


class _HeartbeatFlySto:
    """Minimal FlySto stub for heartbeat coverage tests."""

    def resolve_log_for_file(self, *_args, **_kwargs):
        return None, None, None

    def assign_crew_for_log_id(self, *_args, **_kwargs):
        return None

    def assign_crew_for_log_ids(self, *_args, **_kwargs):
        return None

    def fetch_log_metadata(self, *_args, **_kwargs):
        return {"items": []}

    def resolve_log_source_for_log_id(self, *_args, **_kwargs):
        return None, None

    def ensure_aircraft(self, *_args, **_kwargs):
        return None

    def assign_aircraft_for_signature(self, *_args, **_kwargs):
        return None

    def log_files_to_process(self):
        return 0


def test_reconcile_functions_invoke_heartbeat_per_item(tmp_path: Path):
    report_path = tmp_path / "import_report.json"
    payload = {
        "items": [
            {"flight_id": "f-1", "file_path": str(tmp_path / "a.csv"), "tail_number": "N1"},
            {"flight_id": "f-2", "file_path": str(tmp_path / "b.csv"), "tail_number": "N2"},
            {"flight_id": "f-3", "file_path": str(tmp_path / "c.csv"), "tail_number": "N3"},
        ]
    }
    report_path.write_text(json.dumps(payload))
    flysto = _HeartbeatFlySto()

    for fn in (reconcile_aircraft_from_report, reconcile_metadata_from_report):
        calls = {"n": 0}

        def heartbeat() -> None:
            calls["n"] += 1

        fn(report_path, flysto, heartbeat=heartbeat)
        assert calls["n"] >= 3

    crew_calls = {"n": 0}

    def crew_heartbeat() -> None:
        crew_calls["n"] += 1

    reconcile_crew_from_report(report_path, flysto, heartbeat=crew_heartbeat)
    assert crew_calls["n"] >= 3


class _BatchedCrewFlySto:
    """Stub that records calls to assign_crew_for_log_ids (batched POST)."""

    def __init__(self) -> None:
        self.batch_calls: list[tuple[tuple[str, ...], tuple]] = []

    def resolve_log_for_file(self, *_args, **_kwargs):
        return None, None, None

    def assign_crew_for_log_ids(self, log_ids, crew) -> None:
        names = tuple(
            (entry.get("name"), entry.get("role"), bool(entry.get("is_pic")))
            for entry in (crew or [])
        )
        self.batch_calls.append((tuple(log_ids), names))

    def assign_crew_for_log_id(self, *_args, **_kwargs):
        raise AssertionError(
            "reconcile_crew_from_report should go through assign_crew_for_log_ids"
        )

    def fetch_log_metadata(self, log_id: str):
        # Report that crew is already present so no per-item verify retry
        # fires — this test is about grouping, not about the verify loop.
        return {"items": [{"id": log_id, "annotations": {"crew": [[1, -6]]}}]}


def test_reconcile_crew_groups_identical_crew_into_one_batch(tmp_path: Path):
    report_path = tmp_path / "import_report.json"
    alex_solo = [{"name": "Alex", "role": "Student", "is_pic": True}]
    alex_with_franz = [
        {"name": "Alex", "role": "Student", "is_pic": False},
        {"name": "Franz", "role": "Instructor", "is_pic": False},
    ]
    payload = {
        "items": [
            {"flight_id": "f-1", "flysto_upload_log_id": "log-1", "crew": list(alex_solo)},
            {"flight_id": "f-2", "flysto_upload_log_id": "log-2", "crew": list(alex_solo)},
            {"flight_id": "f-3", "flysto_upload_log_id": "log-3", "crew": list(alex_with_franz)},
            {"flight_id": "f-4", "flysto_upload_log_id": "log-4", "crew": list(alex_with_franz)},
            {"flight_id": "f-5", "flysto_upload_log_id": "log-5", "crew": list(alex_with_franz)},
        ]
    }
    report_path.write_text(json.dumps(payload))
    flysto = _BatchedCrewFlySto()

    updated = reconcile_crew_from_report(report_path, flysto)

    assert updated == 5
    # Two distinct crew tuples → two POSTs total; the three-instructor group
    # is folded into a single call, the two-solo group into another.
    assert len(flysto.batch_calls) == 2
    batches_by_size = sorted(flysto.batch_calls, key=lambda call: len(call[0]))
    assert batches_by_size[0][0] == ("log-1", "log-2")
    assert set(batches_by_size[1][0]) == {"log-3", "log-4", "log-5"}


class _ParallelMetadataFlySto:
    """Stub that records assign_metadata_for_log_id call order + worker thread."""

    def __init__(self) -> None:
        import threading

        self._lock = threading.Lock()
        self.call_log: list[tuple[str, str]] = []

    def assign_metadata_for_log_id(self, log_id, remarks=None, tags=None):
        import threading

        with self._lock:
            self.call_log.append((log_id, threading.current_thread().name))


def test_reconcile_metadata_parallel_calls_execute_off_main_thread(tmp_path: Path):
    import threading

    report_path = tmp_path / "import_report.json"
    items = [
        {
            "flight_id": f"f-{idx}",
            "flysto_upload_log_id": f"log-{idx}",
            "tags": ["cloudahoy"],
            "remarks": f"flight {idx}",
        }
        for idx in range(6)
    ]
    report_path.write_text(json.dumps({"items": items}))
    flysto = _ParallelMetadataFlySto()

    updated = reconcile_metadata_from_report(report_path, flysto, max_workers=4)

    assert updated == 6
    log_ids = {log_id for log_id, _thread in flysto.call_log}
    assert log_ids == {f"log-{idx}" for idx in range(6)}
    thread_names = {thread for _log_id, thread in flysto.call_log}
    # Must have executed on at least one non-main thread — proves dispatch.
    assert not thread_names.issubset({threading.current_thread().name})


def test_reconcile_metadata_max_workers_1_stays_serial(tmp_path: Path):
    import threading

    report_path = tmp_path / "import_report.json"
    items = [
        {
            "flight_id": f"f-{idx}",
            "flysto_upload_log_id": f"log-{idx}",
            "tags": ["cloudahoy"],
            "remarks": f"flight {idx}",
        }
        for idx in range(4)
    ]
    report_path.write_text(json.dumps({"items": items}))
    flysto = _ParallelMetadataFlySto()

    updated = reconcile_metadata_from_report(report_path, flysto, max_workers=1)

    assert updated == 4
    # Serial path must execute entirely on the caller's thread — this is the
    # CLI-compatibility guarantee.
    thread_names = {thread for _log_id, thread in flysto.call_log}
    assert thread_names == {threading.current_thread().name}


def test_reconcile_metadata_skips_already_reconciled_items(tmp_path: Path):
    report_path = tmp_path / "import_report.json"
    items = [
        {
            "flight_id": "f-1",
            "flysto_upload_log_id": "log-1",
            "tags": ["cloudahoy"],
            "metadata_reconciled": True,  # prior worker finished this one
        },
        {
            "flight_id": "f-2",
            "flysto_upload_log_id": "log-2",
            "tags": ["cloudahoy"],
        },
    ]
    report_path.write_text(json.dumps({"items": items}))
    flysto = _ParallelMetadataFlySto()

    updated = reconcile_metadata_from_report(report_path, flysto, max_workers=2)

    assert updated == 1  # only the unfinished item touched FlySto
    assert [log_id for log_id, _thread in flysto.call_log] == ["log-2"]


class _SignatureOnlyFlySto:
    """Stub that fails if resolve_log_source_for_log_id is called."""

    def __init__(self) -> None:
        self.assigned: list[tuple[str | None, str | None]] = []

    def resolve_log_for_file(self, *_args, **_kwargs):
        return None, None, None

    def resolve_log_source_for_log_id(self, *_args, **_kwargs):
        raise AssertionError(
            "resolve_log_source_for_log_id must not fire when the signature is already persisted"
        )

    def ensure_aircraft(self, *_args, **_kwargs):
        return {"id": "aircraft-1"}

    def assign_aircraft_for_signature(
        self,
        aircraft_id: str,
        signature: str | None,
        log_format_id: str = "GenericGpx",
        resolved_format: str | None = None,
    ) -> None:
        self.assigned.append((signature, resolved_format))


def test_reconcile_aircraft_skips_log_source_lookup_when_signature_is_persisted(tmp_path: Path):
    report_path = tmp_path / "import_report.json"
    payload = {
        "items": [
            {
                "flight_id": "flight-1",
                "tail_number": "D-KBUH",
                "file_path": str(tmp_path / "flight.g3x.csv"),
                "flysto_log_id": "log-1",
                # Source system id + format already persisted — the GET is
                # pure waste; the stub raises if it's called.
                "flysto_source_system_id": "system id: D-KBUH",
                "flysto_upload_format": "UnknownGarmin",
            }
        ]
    }
    report_path.write_text(json.dumps(payload))

    flysto = _SignatureOnlyFlySto()
    updated = reconcile_aircraft_from_report(report_path, flysto)

    assert updated == 1
    assert flysto.assigned == [("system id: D-KBUH", "UnknownGarmin")]


def test_reconcile_crew_verify_false_skips_post_assign_fetch(tmp_path: Path):
    """Reapply pass must not fire fetch_log_metadata (verify=False)."""

    class _NoVerifyFlySto:
        def __init__(self) -> None:
            self.batch_calls = 0

        def resolve_log_for_file(self, *_args, **_kwargs):
            return None, None, None

        def assign_crew_for_log_ids(self, log_ids, crew):
            self.batch_calls += 1

        def assign_crew_for_log_id(self, *_args, **_kwargs):
            raise AssertionError("batched path expected")

        def fetch_log_metadata(self, *_args, **_kwargs):
            raise AssertionError("verify=False must not fetch metadata")

    report_path = tmp_path / "import_report.json"
    payload = {
        "items": [
            {
                "flight_id": "f-1",
                "flysto_upload_log_id": "log-1",
                "crew": [{"name": "Alex", "role": "Student", "is_pic": True}],
            }
        ]
    }
    report_path.write_text(json.dumps(payload))
    flysto = _NoVerifyFlySto()

    updated = reconcile_crew_from_report(
        report_path, flysto, verify=False, skip_if_reconciled=False
    )

    assert updated == 1
    assert flysto.batch_calls == 1


def test_reconcile_shared_payload_skips_disk_writes(tmp_path: Path, monkeypatch):
    report_path = tmp_path / "import_report.json"
    initial = {
        "items": [
            {"flight_id": "f-1", "file_path": str(tmp_path / "a.csv"), "tail_number": "N1"},
        ]
    }
    report_path.write_text(json.dumps(initial))
    original_mtime = report_path.stat().st_mtime_ns

    flysto = _HeartbeatFlySto()
    shared = json.loads(report_path.read_text())

    reconcile_aircraft_from_report(report_path, flysto, payload=shared)
    reconcile_crew_from_report(report_path, flysto, payload=shared)
    reconcile_metadata_from_report(report_path, flysto, payload=shared)

    # Shared payload path should not rewrite the report on disk.
    assert report_path.stat().st_mtime_ns == original_mtime
    # The passed-in dict is mutated in place.
    assert "aircraft_reconciled_at" in shared
    assert "metadata_reconciled_at" in shared
