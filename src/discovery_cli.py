import argparse
import os
import sys
from pathlib import Path

from src.config import ConfigError, load_config
from src.discovery import DiscoveryConfig, run_discovery


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="skybridge-discovery",
        description="Run CloudAhoy/FlySto endpoint discovery via web automation",
    )
    parser.add_argument(
        "--discovery-dir",
        default="data/discovery",
        help="Directory for discovery output (default: data/discovery)",
    )
    parser.add_argument(
        "--discovery-upload-file",
        default=None,
        help="Optional path to a file to upload during FlySto discovery",
    )
    parser.add_argument(
        "--headful",
        action="store_true",
        help="Run browser in headful mode for web automation",
    )
    return parser


def run(argv: list[str]) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    os.environ.setdefault("MODE", "web")
    try:
        config = load_config()
    except ConfigError as exc:
        print(f"Config error: {exc}", file=sys.stderr)
        return 2

    headless = config.headless and not args.headful
    output_dir = Path(args.discovery_dir)
    upload_file = Path(args.discovery_upload_file) if args.discovery_upload_file else None

    discovery_path = run_discovery(
        DiscoveryConfig(
            cloudahoy_base_url=config.cloudahoy_web_base_url,
            cloudahoy_email=config.cloudahoy_email,
            cloudahoy_password=config.cloudahoy_password,
            flysto_base_url=config.flysto_web_base_url,
            flysto_email=config.flysto_email,
            flysto_password=config.flysto_password,
            headless=headless,
            output_dir=output_dir,
            cloudahoy_flights_url=config.cloudahoy_flights_url,
            cloudahoy_export_url_template=config.cloudahoy_export_url_template,
            flysto_upload_url=config.flysto_upload_url,
            upload_file=upload_file,
        )
    )
    print(f"Discovery results written to {discovery_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(run(sys.argv[1:]))
