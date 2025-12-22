import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Config:
    cloudahoy_api_key: str
    cloudahoy_base_url: str
    flysto_api_key: str
    flysto_base_url: str
    dry_run: bool
    max_flights: int | None


class ConfigError(ValueError):
    pass


def _get_env(name: str) -> str | None:
    value = os.getenv(name)
    if value is None or value.strip() == "":
        return None
    return value.strip()


def load_config() -> Config:
    cloudahoy_api_key = _get_env("CLOUD_AHOY_API_KEY")
    flysto_api_key = _get_env("FLYSTO_API_KEY")

    missing = [
        name
        for name, value in (
            ("CLOUD_AHOY_API_KEY", cloudahoy_api_key),
            ("FLYSTO_API_KEY", flysto_api_key),
        )
        if value is None
    ]
    if missing:
        raise ConfigError(f"Missing required env vars: {', '.join(missing)}")

    cloudahoy_base_url = _get_env("CLOUD_AHOY_BASE_URL") or "https://api.cloudahoy.com"
    flysto_base_url = _get_env("FLYSTO_BASE_URL") or "https://api.flysto.net"

    dry_run_value = (_get_env("DRY_RUN") or "false").lower()
    dry_run = dry_run_value in {"1", "true", "yes", "on"}

    max_flights_value = _get_env("MAX_FLIGHTS")
    max_flights = int(max_flights_value) if max_flights_value else None

    return Config(
        cloudahoy_api_key=cloudahoy_api_key,
        cloudahoy_base_url=cloudahoy_base_url,
        flysto_api_key=flysto_api_key,
        flysto_base_url=flysto_base_url,
        dry_run=dry_run,
        max_flights=max_flights,
    )
