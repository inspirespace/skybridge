from __future__ import annotations

from dataclasses import dataclass

from src.cloudahoy.client import CloudAhoyClient
from src.flysto.client import FlyStoClient
from src.models import FlightSummary, MigrationResult


@dataclass(frozen=True)
class MigrationStats:
    attempted: int
    succeeded: int
    failed: int


def migrate_flights(
    cloudahoy: CloudAhoyClient,
    flysto: FlyStoClient,
    dry_run: bool = False,
    max_flights: int | None = None,
) -> tuple[list[MigrationResult], MigrationStats]:
    summaries = cloudahoy.list_flights(limit=max_flights)
    results: list[MigrationResult] = []
    succeeded = 0
    failed = 0

    for summary in summaries:
        result = _migrate_single(summary, cloudahoy, flysto, dry_run)
        results.append(result)
        if result.status == "ok":
            succeeded += 1
        else:
            failed += 1

    return results, MigrationStats(
        attempted=len(summaries),
        succeeded=succeeded,
        failed=failed,
    )


def _migrate_single(
    summary: FlightSummary,
    cloudahoy: CloudAhoyClient,
    flysto: FlyStoClient,
    dry_run: bool,
) -> MigrationResult:
    try:
        detail = cloudahoy.fetch_flight(summary.id)
        flysto.upload_flight(detail, dry_run=dry_run)
        return MigrationResult(flight_id=summary.id, status="ok")
    except Exception as exc:  # noqa: BLE001 - surfacing per-flight failure
        return MigrationResult(
            flight_id=summary.id,
            status="error",
            message=str(exc),
        )
