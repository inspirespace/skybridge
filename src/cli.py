import argparse
import getpass
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from src.cloudahoy.client import CloudAhoyClient
from src.models import FlightSummary
from src.config import ConfigError, load_config
from src.discovery import DiscoveryConfig, run_discovery
from src.flysto.client import FlyStoClient
from src.migration import (
    migrate_flights,
    prepare_review,
    reconcile_aircraft_from_report,
    reconcile_crew_from_report,
    reconcile_metadata_from_report,
    verify_import_report,
)
from src.state import MigrationState
from src.web.cloudahoy import CloudAhoyWebClient, CloudAhoyWebConfig
from src.web.flysto import FlyStoWebClient, FlyStoWebConfig


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="skybridge",
        description="Migrate CloudAhoy flights to FlySto",
    )
    parser.add_argument(
        "--guided",
        action="store_true",
        help="Run an interactive guided migration flow",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Fetch from CloudAhoy without uploading to FlySto",
    )
    parser.add_argument(
        "--review",
        action="store_true",
        help="Generate a review manifest and exit without importing",
    )
    parser.add_argument(
        "--review-id",
        default=None,
        help="Review ID required to approve import (from review manifest)",
    )
    parser.add_argument(
        "--review-path",
        default=None,
        help="Path to write the review manifest (default: data/review.json or RUN_ID-based path)",
    )
    parser.add_argument(
        "--approve-import",
        action="store_true",
        help="Allow uploads to FlySto after review",
    )
    parser.add_argument(
        "--import-report",
        default=None,
        help="Path to write an import report after upload (default: data/import_report.json or RUN_ID-based path)",
    )
    parser.add_argument(
        "--max-flights",
        type=int,
        default=None,
        help="Limit number of flights to migrate",
    )
    parser.add_argument(
        "--start-date",
        default=None,
        help="Filter flights on/after this UTC date or datetime (YYYY-MM-DD or ISO8601)",
    )
    parser.add_argument(
        "--end-date",
        default=None,
        help="Filter flights on/before this UTC date or datetime (YYYY-MM-DD or ISO8601)",
    )
    parser.add_argument(
        "--state-path",
        default=None,
        help="Path to SQLite state database (default: data/migration.db or RUN_ID-based path)",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Re-upload flights even if they were already migrated",
    )
    parser.add_argument(
        "--mode",
        choices=["auto", "api", "web", "hybrid"],
        help="Select API or web automation mode (default: auto)",
    )
    parser.add_argument(
        "--headful",
        action="store_true",
        help="Run browser in headful mode for web automation",
    )
    parser.add_argument(
        "--cloudahoy-state-path",
        default="data/cloudahoy_state.json",
        help="Storage state path for CloudAhoy browser session",
    )
    parser.add_argument(
        "--flysto-state-path",
        default="data/flysto_state.json",
        help="Storage state path for FlySto browser session",
    )
    parser.add_argument(
        "--exports-dir",
        default=None,
        help="Download directory for CloudAhoy exports (default: data/cloudahoy_exports or RUN_ID-based path)",
    )
    parser.add_argument(
        "--discover",
        action="store_true",
        help="Run endpoint discovery using web automation and write data/discovery/discovery.json",
    )
    parser.add_argument(
        "--discovery-dir",
        default="data/discovery",
        help="Directory for discovery output",
    )
    parser.add_argument(
        "--discovery-upload-file",
        default=None,
        help="Optional path to a file to upload during FlySto discovery",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Emit per-flight progress logs during import",
    )
    parser.add_argument(
        "--verify-import-report",
        action="store_true",
        help="Verify an existing import report against FlySto without re-importing",
    )
    parser.add_argument(
        "--reconcile-import-report",
        action="store_true",
        help="Reconcile crew/aircraft for an existing import report without re-importing",
    )
    parser.add_argument(
        "--wait-for-processing",
        action="store_true",
        help="Wait for FlySto ingestion to drain, verify, and reconcile aircraft assignments",
    )
    parser.add_argument(
        "--processing-interval",
        type=float,
        default=20.0,
        help="Seconds between FlySto processing queue checks (default: 20)",
    )
    parser.add_argument(
        "--processing-timeout",
        type=float,
        default=3600.0,
        help="Max seconds to wait for FlySto processing queue (default: 3600)",
    )
    return parser


def _read_review_id(path: Path) -> str | None:
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text())
    except json.JSONDecodeError:
        return None
    review_id = payload.get("review_id")
    return review_id if isinstance(review_id, str) and review_id else None


def _summaries_from_review(path: Path) -> list[FlightSummary]:
    payload = json.loads(path.read_text())
    items = payload.get("items", [])
    summaries: list[FlightSummary] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        flight_id = item.get("flight_id")
        if not isinstance(flight_id, str) or not flight_id:
            continue
        started_at = None
        started_raw = item.get("started_at")
        if isinstance(started_raw, str) and started_raw:
            try:
                normalized = started_raw.replace("Z", "+00:00")
                started_at = datetime.fromisoformat(normalized)
            except ValueError:
                started_at = None
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


def _parse_date_bound(value: str, is_end: bool) -> datetime:
    raw = value.strip()
    normalized = raw.replace("Z", "+00:00")
    if "T" not in normalized and len(normalized) == 10:
        dt = datetime.fromisoformat(normalized)
        if is_end:
            dt = dt.replace(hour=23, minute=59, second=59, microsecond=999999)
        else:
            dt = dt.replace(hour=0, minute=0, second=0, microsecond=0)
    else:
        dt = datetime.fromisoformat(normalized)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def _filter_summaries_by_date(
    summaries: list[FlightSummary],
    start_date: datetime | None,
    end_date: datetime | None,
) -> list[FlightSummary]:
    if not start_date and not end_date:
        return summaries
    filtered: list[FlightSummary] = []
    for summary in summaries:
        started_at = summary.started_at
        if started_at is None:
            continue
        if started_at.tzinfo is None:
            started_at = started_at.replace(tzinfo=timezone.utc)
        if start_date and started_at < start_date:
            continue
        if end_date and started_at > end_date:
            continue
        filtered.append(summary)
    return filtered


def _apply_run_paths(args: argparse.Namespace, run_id: str, runs_dir: str) -> tuple[Path, str]:
    log_path = (os.getenv("LOG_PATH") or "").strip()
    if run_id:
        run_dir = Path(runs_dir) / run_id
        run_dir.mkdir(parents=True, exist_ok=True)
        if args.review_path is None:
            args.review_path = str(run_dir / "review.json")
        if args.import_report is None:
            args.import_report = str(run_dir / "import_report.json")
        if args.exports_dir is None:
            args.exports_dir = str(run_dir / "cloudahoy_exports")
        if args.state_path is None:
            args.state_path = str(run_dir / "migration.db")
        if not log_path:
            log_path = str(run_dir / "docker.log")
    else:
        run_dir = Path(runs_dir)
        if args.review_path is None:
            args.review_path = "data/review.json"
        if args.import_report is None:
            args.import_report = "data/import_report.json"
        if args.exports_dir is None:
            args.exports_dir = "data/cloudahoy_exports"
        if args.state_path is None:
            args.state_path = "data/migration.db"
    return run_dir, log_path


def _setup_logging(log_path: str) -> None:
    if not log_path:
        return
    log_file_path = Path(log_path)
    log_file_path.parent.mkdir(parents=True, exist_ok=True)
    log_handle = log_file_path.open("a", encoding="utf-8")

    class _Tee:
        def __init__(self, *streams):
            self._streams = streams

        def write(self, data: str) -> int:
            written = 0
            for stream in self._streams:
                try:
                    written = stream.write(data)
                except Exception:
                    continue
            return written

        def flush(self) -> None:
            for stream in self._streams:
                try:
                    stream.flush()
                except Exception:
                    continue

    sys.stdout = _Tee(sys.stdout, log_handle)
    sys.stderr = _Tee(sys.stderr, log_handle)


def _parse_missing_env_vars(error: ConfigError) -> list[str]:
    prefix = "Missing required env vars: "
    message = str(error)
    if not message.startswith(prefix):
        return []
    missing = message[len(prefix):]
    return [name.strip() for name in missing.split(",") if name.strip()]


def _prompt_env_var(name: str) -> str:
    if "PASSWORD" in name:
        value = getpass.getpass(f"{name}: ")
    else:
        value = input(f"{name}: ").strip()
    return value


def _prompt_for_missing_env_vars(missing: list[str]) -> bool:
    if not missing:
        return False
    print("Missing required credentials. Enter them to continue.")
    for name in missing:
        value = _prompt_env_var(name)
        if value:
            os.environ[name] = value
    return True


def run(argv: list[str]) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    runs_dir = (os.getenv("RUNS_DIR") or "data/runs").strip()
    run_id = (os.getenv("RUN_ID") or "").strip()

    if args.guided and not run_id:
        run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

    run_dir, log_path = _apply_run_paths(args, run_id, runs_dir)
    if not args.guided:
        _setup_logging(log_path)

    try:
        config = load_config()
    except ConfigError as exc:
        missing = _parse_missing_env_vars(exc)
        if missing and _prompt_for_missing_env_vars(missing):
            try:
                config = load_config()
            except ConfigError as exc_retry:
                print(f"Config error: {exc_retry}", file=sys.stderr)
                return 2
        else:
            print(f"Config error: {exc}", file=sys.stderr)
            return 2

    dry_run = args.dry_run or config.dry_run
    max_flights = args.max_flights or config.max_flights
    state = MigrationState(Path(args.state_path))

    mode = (args.mode or config.mode).lower()
    if mode not in {"auto", "api", "web", "hybrid"}:
        print(f"Unsupported mode: {mode}", file=sys.stderr)
        return 2
    headless = config.headless and not args.headful

    if mode == "auto":
        mode = "api"

    start_date = (
        _parse_date_bound(args.start_date, is_end=False)
        if args.start_date
        else None
    )
    end_date = (
        _parse_date_bound(args.end_date, is_end=True)
        if args.end_date
        else None
    )

    if mode in {"api", "hybrid"} and not config.flysto_session_cookie:
        missing = []
        if not config.flysto_email:
            missing.append("FLYSTO_EMAIL")
        if not config.flysto_password:
            missing.append("FLYSTO_PASSWORD")
        if missing and _prompt_for_missing_env_vars(missing):
            try:
                config = load_config()
            except ConfigError as exc_retry:
                print(f"Config error: {exc_retry}", file=sys.stderr)
                return 2

    if mode in {"web", "hybrid"}:
        cloudahoy = CloudAhoyWebClient(
            CloudAhoyWebConfig(
                base_url=config.cloudahoy_web_base_url,
                email=config.cloudahoy_email,
                password=config.cloudahoy_password,
                flights_url=config.cloudahoy_flights_url,
                export_url_template=config.cloudahoy_export_url_template,
                storage_state_path=Path(args.cloudahoy_state_path),
                downloads_dir=Path(args.exports_dir),
                headless=headless,
            )
        )
        if mode == "web":
            cloudahoy_client = cloudahoy
        else:
            cloudahoy_client = CloudAhoyClient(
                api_key=config.cloudahoy_api_key,
                base_url=config.cloudahoy_base_url,
                email=config.cloudahoy_email or "",
                password=config.cloudahoy_password or "",
                exports_dir=Path(args.exports_dir),
                export_format=config.cloudahoy_export_format,
                export_formats=config.cloudahoy_export_formats,
            )

        flysto = FlyStoWebClient(
            FlyStoWebConfig(
                base_url=config.flysto_web_base_url,
                email=config.flysto_email,
                password=config.flysto_password,
                upload_url=config.flysto_upload_url,
                storage_state_path=Path(args.flysto_state_path),
                headless=headless,
            )
        )

        if args.discover:
            discovery_path = run_discovery(
                DiscoveryConfig(
                    cloudahoy_base_url=config.cloudahoy_web_base_url,
                    cloudahoy_email=config.cloudahoy_email,
                    cloudahoy_password=config.cloudahoy_password,
                    flysto_base_url=config.flysto_web_base_url,
                    flysto_email=config.flysto_email,
                    flysto_password=config.flysto_password,
                    headless=headless,
                    output_dir=Path(args.discovery_dir),
                    cloudahoy_flights_url=config.cloudahoy_flights_url,
                    cloudahoy_export_url_template=config.cloudahoy_export_url_template,
                    flysto_upload_url=config.flysto_upload_url,
                    upload_file=(
                        Path(args.discovery_upload_file)
                        if args.discovery_upload_file
                        else None
                    ),
                )
            )
            print(f"Discovery results written to {discovery_path}")
            return 0
    else:
        cloudahoy_client = CloudAhoyClient(
            api_key=config.cloudahoy_api_key,
            base_url=config.cloudahoy_base_url,
            email=config.cloudahoy_email or "",
            password=config.cloudahoy_password or "",
            exports_dir=Path(args.exports_dir),
            export_format=config.cloudahoy_export_format,
            export_formats=config.cloudahoy_export_formats,
        )
        flysto = FlyStoClient(
            api_key=config.flysto_api_key or "",
            base_url=config.flysto_base_url,
            upload_url=config.flysto_log_upload_url,
            session_cookie=config.flysto_session_cookie,
            include_metadata=config.flysto_include_metadata,
            api_version=config.flysto_api_version,
            email=config.flysto_email,
            password=config.flysto_password,
            min_request_interval=config.flysto_min_request_interval,
            max_request_retries=config.flysto_max_request_retries,
        )
        needs_flysto = not (args.review or dry_run)
        if needs_flysto and not flysto.prepare():
            print(
                "FlySto API not available. Verify credentials or set "
                "FLYSTO_BASE_URL/FLYSTO_SESSION_COOKIE.",
                file=sys.stderr,
            )
            return 2

    summaries = None
    if mode == "hybrid":
        try:
            summaries = cloudahoy.list_flights(limit=max_flights)
        except Exception as exc:
            print(
                f"Warning: web flight listing failed, falling back to API: {exc}",
                file=sys.stderr,
            )
    if (start_date or end_date) and summaries is None and isinstance(
        cloudahoy_client, CloudAhoyClient
    ):
        summaries = cloudahoy_client.list_flights(limit=max_flights)

    if summaries is not None:
        summaries = _filter_summaries_by_date(summaries, start_date, end_date)
        if max_flights:
            summaries = summaries[:max_flights]

    def _stamp() -> str:
        return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    if args.guided:
        try:
            from rich.console import Console
        except Exception as exc:
            print(
                f"Guided mode requires the 'rich' package. {exc}",
                file=sys.stderr,
            )
            print("Install dependencies or use the devcontainer image.", file=sys.stderr)
            return 2
        try:
            from src.guided import run_guided
        except Exception as exc:
            print(f"Guided mode failed to load: {exc}", file=sys.stderr)
            return 2

        console = Console()
        if not isinstance(cloudahoy_client, CloudAhoyClient) or not isinstance(
            flysto, FlyStoClient
        ):
            print("Guided mode requires API clients (mode=api).", file=sys.stderr)
            return 2
        try:
            return run_guided(
                console=console,
                cloudahoy=cloudahoy_client,
                flysto=flysto,
                state=state,
                run_dir=Path(runs_dir) / run_id if run_id else Path(runs_dir),
                review_path=Path(args.review_path),
                report_path=Path(args.import_report),
                exports_dir=Path(args.exports_dir),
                summaries=summaries,
                max_flights=max_flights,
                force=args.force,
                processing_interval=args.processing_interval,
                processing_timeout=args.processing_timeout,
                run_id=run_id,
                setup_logging=_setup_logging,
            )
        except KeyboardInterrupt:
            print("\nGuided run cancelled.")
            return 130

    if args.verify_import_report:
        if not Path(args.import_report).exists():
            print(f"Import report not found: {args.import_report}", file=sys.stderr)
            return 2
        if not flysto.prepare():
            print(
                "FlySto API not available. Verify credentials or set "
                "FLYSTO_BASE_URL/FLYSTO_SESSION_COOKIE.",
                file=sys.stderr,
            )
            return 2
        summary = verify_import_report(Path(args.import_report), flysto)
        print(
            "Verify summary: attempted={attempted} resolved={resolved} missing={missing}".format(
                attempted=summary.get("attempted", 0),
                resolved=summary.get("resolved", 0),
                missing=summary.get("missing", 0),
            ),
            flush=True,
        )
        return 0 if summary.get("missing", 0) == 0 else 1

    if args.reconcile_import_report:
        report_path = Path(args.import_report)
        if not report_path.exists():
            print(f"Import report not found: {args.import_report}", file=sys.stderr)
            return 2
        if not flysto.prepare():
            print(
                "FlySto API not available. Verify credentials or set "
                "FLYSTO_BASE_URL/FLYSTO_SESSION_COOKIE.",
                file=sys.stderr,
            )
            return 2
        if args.wait_for_processing:
            start_wait = time.monotonic()
            while True:
                n_files = flysto.log_files_to_process()
                if n_files is None:
                    print(
                        f"{_stamp()} FlySto processing queue unknown",
                        flush=True,
                    )
                    break
                print(
                    f"{_stamp()} FlySto processing queue {n_files}",
                    flush=True,
                )
                if n_files <= 0:
                    break
                if time.monotonic() - start_wait > args.processing_timeout:
                    print(
                        f"{_stamp()} FlySto processing wait timed out after {args.processing_timeout:.0f}s",
                        flush=True,
                    )
                    break
                time.sleep(args.processing_interval)

        summary = verify_import_report(report_path, flysto)
        print(
            "Verify summary: attempted={attempted} resolved={resolved} missing={missing}".format(
                attempted=summary.get("attempted", 0),
                resolved=summary.get("resolved", 0),
                missing=summary.get("missing", 0),
            ),
            flush=True,
        )
        review_path = Path(args.review_path) if args.review_path else None
        cloudahoy_for_reconcile = (
            cloudahoy_client if isinstance(cloudahoy_client, CloudAhoyClient) else None
        )
        reconciled = reconcile_aircraft_from_report(report_path, flysto)
        print(
            f"{_stamp()} FlySto aircraft reconciled {reconciled}",
            flush=True,
        )
        reconciled_crew = reconcile_crew_from_report(
            report_path,
            flysto,
            review_path,
            cloudahoy_for_reconcile,
        )
        print(
            f"{_stamp()} FlySto crew reconciled {reconciled_crew}",
            flush=True,
        )
        reconciled_metadata = reconcile_metadata_from_report(report_path, flysto)
        print(
            f"{_stamp()} FlySto metadata reconciled {reconciled_metadata}",
            flush=True,
        )
        return 0 if summary.get("missing", 0) == 0 else 1

    if args.review or (not dry_run and not args.approve_import):
        _, review_id = prepare_review(
            cloudahoy=cloudahoy_client,
            summaries=summaries,
            max_flights=max_flights,
            state=state,
            force=args.force,
            output_path=Path(args.review_path),
        )
        if not args.review and not dry_run:
            print(
                "Review required before upload. "
                "Check the manifest and rerun with --approve-import to proceed."
            )
        else:
            print(f"Review manifest written to {args.review_path}")
            print(f"Review ID: {review_id}")
        return 0

    if args.approve_import and not dry_run:
        review_id = _read_review_id(Path(args.review_path))
        if not review_id and args.review_id:
            print(
                "Review ID not found in manifest; proceeding with provided review ID.",
                file=sys.stderr,
            )
            review_id = args.review_id
        if not review_id:
            print(
                "Review ID not found. Re-run review to generate a manifest.",
                file=sys.stderr,
            )
            return 2
        if not args.review_id:
            print(
                "Review ID required. Re-run with --review-id <id> from the manifest.",
                file=sys.stderr,
            )
            return 2
        if args.review_id != review_id:
            print(
                "Review ID does not match the manifest. Aborting.",
                file=sys.stderr,
            )
            return 2

    if args.approve_import and args.review_path and Path(args.review_path).exists():
        summaries = _summaries_from_review(Path(args.review_path))

    start_times: dict[str, float] = {}
    start_all = time.monotonic()

    step_times: dict[tuple[str, str], float] = {}

    def _step_start(flight_id: str, step: str) -> None:
        step_times[(flight_id, step)] = time.monotonic()

    def _step_done(flight_id: str, step: str) -> str:
        key = (flight_id, step)
        if key not in step_times:
            return ""
        return f" ({time.monotonic() - step_times[key]:.1f}s)"

    def progress(event: str, payload: dict) -> None:
        if not args.verbose:
            return
        if event == "start":
            flight_id = payload.get("flight_id")
            start_times[flight_id] = time.monotonic()
            print(f"{_stamp()} START {flight_id}", flush=True)
        elif event == "cloudahoy_fetch_start":
            _step_start(payload.get("flight_id"), "cloudahoy_fetch")
            print(f"{_stamp()} CloudAhoy fetch {payload.get('flight_id')}", flush=True)
        elif event == "cloudahoy_fetch_done":
            duration = _step_done(payload.get("flight_id"), "cloudahoy_fetch")
            print(
                f"{_stamp()} CloudAhoy fetched {payload.get('flight_id')} ({payload.get('file_path')}){duration}",
                flush=True,
            )
        elif event == "flysto_upload_start":
            _step_start(payload.get("flight_id"), "flysto_upload")
            print(f"{_stamp()} FlySto upload {payload.get('flight_id')}", flush=True)
        elif event == "flysto_upload_done":
            duration = _step_done(payload.get("flight_id"), "flysto_upload")
            print(f"{_stamp()} FlySto uploaded {payload.get('flight_id')}{duration}", flush=True)
        elif event == "flysto_assign_aircraft_file_start":
            _step_start(payload.get("flight_id"), "flysto_assign_aircraft")
            print(
                f"{_stamp()} FlySto assign aircraft file {payload.get('flight_id')} -> {payload.get('aircraft_id')}",
                flush=True,
            )
        elif event == "flysto_assign_aircraft_file_done":
            duration = _step_done(payload.get("flight_id"), "flysto_assign_aircraft")
            print(
                f"{_stamp()} FlySto assigned aircraft file {payload.get('flight_id')}{duration}",
                flush=True,
            )
        elif event == "flysto_assign_crew_start":
            _step_start(payload.get("flight_id"), "flysto_assign_crew")
            print(
                f"{_stamp()} FlySto assign crew {payload.get('flight_id')} ({payload.get('crew_count')} members)",
                flush=True,
            )
        elif event == "flysto_assign_crew_done":
            duration = _step_done(payload.get("flight_id"), "flysto_assign_crew")
            print(
                f"{_stamp()} FlySto assigned crew {payload.get('flight_id')}{duration}",
                flush=True,
            )
        elif event == "flysto_assign_metadata_start":
            _step_start(payload.get("flight_id"), "flysto_assign_metadata")
            print(
                f"{_stamp()} FlySto assign metadata {payload.get('flight_id')} (remarks={payload.get('has_remarks')}, tags={payload.get('tag_count')})",
                flush=True,
            )
        elif event == "flysto_assign_metadata_done":
            duration = _step_done(payload.get("flight_id"), "flysto_assign_metadata")
            print(
                f"{_stamp()} FlySto assigned metadata {payload.get('flight_id')}{duration}",
                flush=True,
            )
        elif event == "flysto_assign_aircraft_group":
            print(
                f"{_stamp()} FlySto assign aircraft group {payload.get('tail_number')} -> {payload.get('aircraft_id')}",
                flush=True,
            )
        elif event == "flysto_processing_queue":
            print(
                f"{_stamp()} FlySto processing queue {payload.get('n_files')}",
                flush=True,
            )
        elif event == "end":
            flight_id = payload.get("flight_id")
            status = payload.get("status")
            message = payload.get("message")
            suffix = f": {message}" if message else ""
            elapsed = ""
            if flight_id in start_times:
                elapsed = f" ({time.monotonic() - start_times[flight_id]:.1f}s)"
            print(f"{_stamp()} DONE {flight_id} {status}{suffix}{elapsed}", flush=True)

    results, stats = migrate_flights(
        cloudahoy=cloudahoy_client,
        flysto=flysto,
        dry_run=dry_run,
        summaries=summaries,
        max_flights=max_flights,
        state=state,
        force=args.force,
        report_path=Path(args.import_report) if args.approve_import and not dry_run else None,
        review_id=args.review_id,
        progress=progress,
    )

    for result in results:
        if result.status == "ok":
            print(f"{_stamp()} OK {result.flight_id}", flush=True)
        elif result.status == "skipped":
            print(f"{_stamp()} SKIP {result.flight_id}: {result.message}", flush=True)
        else:
            print(f"{_stamp()} ERR {result.flight_id}: {result.message}", flush=True)

    total_elapsed = time.monotonic() - start_all
    print(
        "Summary: attempted={attempted} succeeded={succeeded} failed={failed}".format(
            attempted=stats.attempted,
            succeeded=stats.succeeded,
            failed=stats.failed,
        )
        + f" duration={total_elapsed:.1f}s",
        flush=True,
    )
    if args.approve_import and not dry_run:
        print(f"Import report written to {args.import_report}", flush=True)

    if (
        args.wait_for_processing
        and args.approve_import
        and not dry_run
        and args.import_report
    ):
        start_wait = time.monotonic()
        while True:
            n_files = flysto.log_files_to_process()
            if n_files is None:
                print(
                    f"{_stamp()} FlySto processing queue unknown",
                    flush=True,
                )
                break
            print(
                f"{_stamp()} FlySto processing queue {n_files}",
                flush=True,
            )
            if n_files <= 0:
                break
            if time.monotonic() - start_wait > args.processing_timeout:
                print(
                    f"{_stamp()} FlySto processing wait timed out after {args.processing_timeout:.0f}s",
                    flush=True,
                )
                break
            time.sleep(args.processing_interval)

        report_path = Path(args.import_report)
        summary = verify_import_report(report_path, flysto)
        print(
            "Verify summary: attempted={attempted} resolved={resolved} missing={missing}".format(
                attempted=summary.get("attempted", 0),
                resolved=summary.get("resolved", 0),
                missing=summary.get("missing", 0),
            ),
            flush=True,
        )
        review_path = Path(args.review_path) if args.review_path else None
        cloudahoy_for_reconcile = (
            cloudahoy_client if isinstance(cloudahoy_client, CloudAhoyClient) else None
        )
        reconciled = reconcile_aircraft_from_report(report_path, flysto)
        print(
            f"{_stamp()} FlySto aircraft reconciled {reconciled}",
            flush=True,
        )
        reconciled_crew = reconcile_crew_from_report(
            report_path,
            flysto,
            review_path,
            cloudahoy_for_reconcile,
        )
        print(
            f"{_stamp()} FlySto crew reconciled {reconciled_crew}",
            flush=True,
        )
        reconciled_metadata = reconcile_metadata_from_report(report_path, flysto)
        print(
            f"{_stamp()} FlySto metadata reconciled {reconciled_metadata}",
            flush=True,
        )
    return 0 if stats.failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(run(sys.argv[1:]))
