import argparse
import sys
from pathlib import Path

from src.cloudahoy.client import CloudAhoyClient
from src.config import ConfigError, load_config
from src.flysto.client import FlyStoClient
from src.migration import migrate_flights
from src.state import MigrationState


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

    cloudahoy = CloudAhoyClient(
        api_key=config.cloudahoy_api_key,
        base_url=config.cloudahoy_base_url,
    )
    flysto = FlyStoClient(
        api_key=config.flysto_api_key,
        base_url=config.flysto_base_url,
    )

    results, stats = migrate_flights(
        cloudahoy=cloudahoy,
        flysto=flysto,
        dry_run=dry_run,
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
