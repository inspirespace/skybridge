import argparse
import json
import sys
from pathlib import Path

from src.cloudahoy.client import CloudAhoyClient
from src.config import ConfigError, load_config
from src.discovery import DiscoveryConfig, run_discovery
from src.flysto.client import FlyStoClient
from src.migration import migrate_flights, prepare_review
from src.state import MigrationState
from src.web.cloudahoy import CloudAhoyWebClient, CloudAhoyWebConfig
from src.web.flysto import FlyStoWebClient, FlyStoWebConfig


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="cloudahoy2flysto",
        description="Migrate CloudAhoy flights to FlySto",
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
        default="data/review.json",
        help="Path to write the review manifest (default: data/review.json)",
    )
    parser.add_argument(
        "--approve-import",
        action="store_true",
        help="Allow uploads to FlySto after review",
    )
    parser.add_argument(
        "--max-flights",
        type=int,
        default=None,
        help="Limit number of flights to migrate",
    )
    parser.add_argument(
        "--state-path",
        default="data/migration.db",
        help="Path to SQLite state database (default: data/migration.db)",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Re-upload flights even if they were already migrated",
    )
    parser.add_argument(
        "--mode",
        choices=["api", "web", "hybrid"],
        help="Select API or web automation mode",
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
        default="data/cloudahoy_exports",
        help="Download directory for CloudAhoy exports",
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
    return parser


def run(argv: list[str]) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        config = load_config()
    except ConfigError as exc:
        print(f"Config error: {exc}", file=sys.stderr)
        return 2

    dry_run = args.dry_run or config.dry_run
    max_flights = args.max_flights or config.max_flights
    state = MigrationState(Path(args.state_path))

    mode = (args.mode or config.mode).lower()
    if mode not in {"api", "web", "hybrid"}:
        print(f"Unsupported mode: {mode}", file=sys.stderr)
        return 2
    headless = config.headless and not args.headful

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
        print("API-only mode is not implemented for FlySto yet.", file=sys.stderr)
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

    results, stats = migrate_flights(
        cloudahoy=cloudahoy_client,
        flysto=flysto,
        dry_run=dry_run,
        summaries=summaries,
        max_flights=max_flights,
        state=state,
        force=args.force,
    )

    for result in results:
        if result.status == "ok":
            print(f"OK {result.flight_id}")
        elif result.status == "skipped":
            print(f"SKIP {result.flight_id}: {result.message}")
        else:
            print(f"ERR {result.flight_id}: {result.message}")

    print(
        "Summary: attempted={attempted} succeeded={succeeded} failed={failed}".format(
            attempted=stats.attempted,
            succeeded=stats.succeeded,
            failed=stats.failed,
        )
    )
    return 0 if stats.failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(run(sys.argv[1:]))


def _read_review_id(path: Path) -> str | None:
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text())
    except json.JSONDecodeError:
        return None
    review_id = payload.get("review_id")
    return review_id if isinstance(review_id, str) and review_id else None
