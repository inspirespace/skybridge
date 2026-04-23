"""src/core/guided.py module."""
from __future__ import annotations

import json
import os
import time
from collections import Counter
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.progress import (
    BarColumn,
    Progress,
    SpinnerColumn,
    TaskProgressColumn,
    TextColumn,
    TimeElapsedColumn,
    TimeRemainingColumn,
)
from rich.prompt import Confirm, IntPrompt, Prompt
from rich.table import Table

from src.core.cloudahoy.client import CloudAhoyClient
from src.core.flysto.client import FlyStoClient
from src.core.migration import (
    migrate_flights,
    prepare_review,
    reconcile_aircraft_from_report,
    reconcile_crew_from_report,
    reconcile_metadata_from_report,
    verify_import_report,
)
from src.core.models import FlightSummary
from src.core.state import MigrationState
from src.core.time_utils import (
    filter_summaries_by_date as _filter_summaries_by_date,
    parse_date_bound as _parse_date_bound,
    parse_iso_z,
)


@dataclass
class GuidedOptions:
    max_flights: int
    force: bool
    wait_for_processing: bool
    verify_after_import: bool
    reconcile_after_import: bool
    run_id: str
    export_formats: str
    start_date: str | None = None
    end_date: str | None = None


def _timestamp() -> str:
    """Internal helper for timestamp."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _parse_started_at(value: str | None) -> datetime | None:
    """Internal helper for parse started at."""
    if not value:
        return None
    try:
        return parse_iso_z(value)
    except ValueError:
        return None


def _summarize_review(path: Path) -> dict[str, Any]:
    """Internal helper for summarize review."""
    payload = json.loads(path.read_text())
    items = payload.get("items", [])
    tails = Counter()
    dates: list[datetime] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        tail = item.get("tail_number")
        if isinstance(tail, str) and tail:
            tails[tail] += 1
        started_at = _parse_started_at(item.get("started_at"))
        if started_at:
            dates.append(started_at)
    min_date = min(dates) if dates else None
    max_date = max(dates) if dates else None
    summary = {
        "count": len(items),
        "min_date": min_date,
        "max_date": max_date,
        "tails": tails,
        "min_date_iso": min_date.isoformat() if min_date else None,
        "max_date_iso": max_date.isoformat() if max_date else None,
    }
    return summary


def _render_review_summary(console: Console, summary: dict[str, Any]) -> None:
    """Internal helper for render review summary."""
    count = summary.get("count", 0)
    min_date = summary.get("min_date")
    max_date = summary.get("max_date")
    tails: Counter = summary.get("tails", Counter())
    table = Table(title="Review Summary", box=box.SIMPLE, show_edge=False)
    table.add_column("Metric")
    table.add_column("Value")
    table.add_row("Flights", str(count))
    if min_date and max_date:
        table.add_row(
            "Date range",
            f"{min_date.date().isoformat()} -> {max_date.date().isoformat()}",
        )
    else:
        table.add_row("Date range", "Unknown")
    if tails:
        top = ", ".join(f"{tail} ({count})" for tail, count in tails.most_common(5))
        table.add_row("Top tails", top)
    else:
        table.add_row("Top tails", "Unknown")
    console.print(table)


def _write_guided_summary(
    run_dir: Path,
    options: GuidedOptions,
    review_id: str | None,
    summary: dict[str, Any] | None,
) -> None:
    """Internal helper for write guided summary."""
    summary_payload: dict[str, Any] = {}
    if summary:
        summary_payload = dict(summary)
        if isinstance(summary_payload.get("tails"), Counter):
            summary_payload["tails"] = dict(summary_payload["tails"])
        if isinstance(summary_payload.get("min_date"), datetime):
            summary_payload["min_date"] = summary_payload["min_date"].isoformat()
        if isinstance(summary_payload.get("max_date"), datetime):
            summary_payload["max_date"] = summary_payload["max_date"].isoformat()
    payload = {
        "generated_at": _timestamp(),
        "run_id": options.run_id,
        "max_flights": options.max_flights,
        "start_date": options.start_date,
        "end_date": options.end_date,
        "export_formats": options.export_formats,
        "force": options.force,
        "wait_for_processing": options.wait_for_processing,
        "verify_after_import": options.verify_after_import,
        "reconcile_after_import": options.reconcile_after_import,
        "review_id": review_id,
        "review_summary": summary_payload,
    }
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "guided.json").write_text(json.dumps(payload, indent=2))


def _prompt_guided_options(
    console: Console,
    default_max: int,
    run_id: str,
) -> GuidedOptions:
    """Internal helper for prompt guided options."""
    console.print(Panel.fit("Skybridge guided migration", style="bold"))
    max_flights = IntPrompt.ask("Max flights to import", default=default_max)
    force = Confirm.ask("Force reimport existing flights?", default=False)
    start_date = Prompt.ask("Start date (YYYY-MM-DD, optional)", default="").strip()
    end_date = Prompt.ask("End date (YYYY-MM-DD, optional)", default="").strip()
    start_date = start_date or None
    end_date = end_date or None
    wait_for_processing = True
    verify_after_import = True
    reconcile_after_import = True
    export_formats = os.getenv("CLOUD_AHOY_EXPORT_FORMATS") or os.getenv(
        "CLOUD_AHOY_EXPORT_FORMAT"
    ) or "g3x,gpx"
    export_formats = Prompt.ask("Export formats (comma-separated)", default=export_formats)
    return GuidedOptions(
        max_flights=max_flights,
        force=force,
        wait_for_processing=wait_for_processing,
        verify_after_import=verify_after_import,
        reconcile_after_import=reconcile_after_import,
        run_id=run_id,
        export_formats=export_formats,
        start_date=start_date,
        end_date=end_date,
    )


def _preflight_checks(console: Console, cloudahoy: CloudAhoyClient, flysto: FlyStoClient) -> bool:
    """Internal helper for preflight checks."""
    table = Table(title="Preflight Checks", box=box.SIMPLE, show_edge=False)
    table.add_column("Check")
    table.add_column("Status")

    ok = True
    try:
        cloudahoy.list_flights(limit=1)
        table.add_row("CloudAhoy connectivity", "OK")
    except Exception as exc:
        ok = False
        table.add_row("CloudAhoy connectivity", f"FAILED ({exc})")

    try:
        if flysto.prepare():
            table.add_row("FlySto connectivity", "OK")
        else:
            ok = False
            table.add_row("FlySto connectivity", "FAILED (auth)")
    except Exception as exc:
        ok = False
        table.add_row("FlySto connectivity", f"FAILED ({exc})")

    console.print(table)
    return ok


def _build_progress(console: Console, total: int) -> Progress:
    """Internal helper for build progress."""
    return Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        TimeElapsedColumn(),
        TimeRemainingColumn(),
        console=console,
    )


def _progress_callback(progress: Progress, task_id: int, console: Console) -> Callable[[str, dict], None]:
    """Internal helper for progress callback."""
    def handler(event: str, payload: dict) -> None:
        """Handle handler."""
        if event == "start":
            flight_id = payload.get("flight_id") or "flight"
            progress.update(task_id, description=f"Importing {flight_id}")
        elif event == "end":
            status = payload.get("status") or "ok"
            flight_id = payload.get("flight_id") or "flight"
            progress.advance(task_id, 1)
            console.log(f"{_timestamp()} {flight_id} {status}")
        elif event == "flysto_processing_queue":
            n_files = payload.get("n_files")
            if isinstance(n_files, int):
                console.log(f"{_timestamp()} FlySto queue {n_files}")
    return handler


def _summaries_from_review(path: Path) -> list[FlightSummary]:
    """Internal helper for summaries from review."""
    payload = json.loads(path.read_text())
    items = payload.get("items", [])
    summaries: list[FlightSummary] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        flight_id = item.get("flight_id")
        if not isinstance(flight_id, str) or not flight_id:
            continue
        started_at = _parse_started_at(item.get("started_at"))
        summaries.append(
            FlightSummary(
                id=flight_id,
                started_at=started_at,
                duration_seconds=item.get("duration_seconds"),
                aircraft_type=item.get("aircraft_type"),
                tail_number=item.get("tail_number"),
            )
        )
    return summaries


def run_guided(
    *,
    console: Console,
    cloudahoy: CloudAhoyClient,
    flysto: FlyStoClient,
    state: MigrationState,
    run_dir: Path,
    review_path: Path,
    report_path: Path,
    exports_dir: Path,
    summaries: list[FlightSummary] | None,
    max_flights: int | None,
    force: bool,
    processing_interval: float,
    processing_timeout: float,
    run_id: str,
    setup_logging: Callable[[str], None] | None = None,
) -> int:
    """Handle run guided."""
    default_max = max_flights or 50
    console.print("Running preflight checks...")
    preflight_ok = _preflight_checks(console, cloudahoy, flysto)
    if not preflight_ok and not Confirm.ask("Continue anyway?", default=False):
        console.print("Aborted.")
        return 1
    options = _prompt_guided_options(console, default_max, run_id)

    run_dir = run_dir.parent / options.run_id
    review_path = run_dir / "review.json"
    report_path = run_dir / "import_report.json"
    exports_dir = run_dir / "cloudahoy_exports"
    state = MigrationState(run_dir / "migration.db")
    if setup_logging:
        setup_logging(str(run_dir / "docker.log"))
    if hasattr(cloudahoy, "exports_dir"):
        try:
            cloudahoy = replace(cloudahoy, exports_dir=exports_dir)
        except Exception:
            pass
    if hasattr(cloudahoy, "export_formats"):
        try:
            export_formats = [
                fmt.strip()
                for fmt in options.export_formats.replace(";", ",").split(",")
                if fmt.strip()
            ]
            cloudahoy = replace(cloudahoy, export_formats=export_formats)
        except Exception:
            pass

    console.print(f"Using run dir: {run_dir}")
    console.print("Running review...")
    if summaries is None:
        summaries = cloudahoy.list_flights(limit=options.max_flights)
    if options.start_date or options.end_date:
        start_date = (
            _parse_date_bound(options.start_date, is_end=False)
            if options.start_date
            else None
        )
        end_date = (
            _parse_date_bound(options.end_date, is_end=True)
            if options.end_date
            else None
        )
        summaries = _filter_summaries_by_date(summaries, start_date, end_date)
    if options.max_flights:
        summaries = summaries[: options.max_flights]

    _, review_id = prepare_review(
        cloudahoy=cloudahoy,
        summaries=summaries,
        max_flights=None,
        state=state,
        force=options.force,
        output_path=review_path,
    )
    summary = _summarize_review(review_path)
    _render_review_summary(console, summary)
    _write_guided_summary(run_dir, options, review_id, summary)

    if not Confirm.ask("Proceed with import?", default=True):
        console.print("Aborted before import.")
        return 1

    console.print("Starting import...")
    import_summaries = _summaries_from_review(review_path)
    with _build_progress(console, summary.get("count", 0)) as progress:
        task_id = progress.add_task("Uploading", total=summary.get("count", 0))
        results, stats = migrate_flights(
            cloudahoy=cloudahoy,
            flysto=flysto,
            dry_run=False,
            summaries=import_summaries,
            max_flights=None,
            state=state,
            force=options.force,
            report_path=report_path,
            review_id=review_id,
            progress=_progress_callback(progress, task_id, console),
        )

    console.print(
        f"Import summary: attempted={stats.attempted} succeeded={stats.succeeded} failed={stats.failed}"
    )
    if stats.failed:
        console.print("Some flights failed. Check the report for details.")

    if options.wait_for_processing:
        console.print("Waiting for FlySto processing queue to drain...")
        start_wait = time.monotonic()
        while True:
            n_files = flysto.log_files_to_process()
            if n_files is None:
                console.print("FlySto processing queue unknown.")
                break
            console.print(f"FlySto processing queue: {n_files}")
            if n_files <= 0:
                break
            if time.monotonic() - start_wait > processing_timeout:
                console.print("Processing wait timed out.")
                break
            time.sleep(processing_interval)

    if options.verify_after_import:
        console.print("Verifying import report...")
        summary_verify = verify_import_report(report_path, flysto)
        console.print(
            f"Verify summary: attempted={summary_verify.get('attempted', 0)} "
            f"resolved={summary_verify.get('resolved', 0)} "
            f"missing={summary_verify.get('missing', 0)}"
        )

    if options.reconcile_after_import:
        console.print("Reconciling crew/aircraft...")
        reconciled_aircraft = reconcile_aircraft_from_report(report_path, flysto)
        reconciled_crew = reconcile_crew_from_report(
            report_path,
            flysto,
            review_path,
            cloudahoy,
        )
        reconciled_metadata = reconcile_metadata_from_report(report_path, flysto)
        console.print(
            "Reconciled aircraft={aircraft} crew={crew} metadata={metadata}".format(
                aircraft=reconciled_aircraft,
                crew=reconciled_crew,
                metadata=reconciled_metadata,
            )
        )
        # Crew can be cleared by late FlySto post-processing; reapply after processing drains.
        start_wait = time.monotonic()
        while True:
            n_files = flysto.log_files_to_process()
            if n_files is None or n_files <= 0:
                break
            if time.monotonic() - start_wait > processing_timeout:
                break
            time.sleep(processing_interval)
        reconciled_crew = reconcile_crew_from_report(
            report_path,
            flysto,
            review_path,
            cloudahoy,
        )
        console.print(f"Reconciled crew (post-processing)={reconciled_crew}")

    console.print(
        Panel.fit(
            f"Done. Artifacts:\n- {review_path}\n- {report_path}\n- {exports_dir}\n- {run_dir / 'docker.log'}",
            title="Summary",
        )
    )
    return 0
