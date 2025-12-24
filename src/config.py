import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Config:
    cloudahoy_api_key: str | None
    cloudahoy_base_url: str
    cloudahoy_email: str | None
    cloudahoy_password: str | None
    cloudahoy_web_base_url: str
    cloudahoy_flights_url: str | None
    cloudahoy_export_url_template: str | None
    flysto_api_key: str | None
    flysto_base_url: str
    flysto_email: str | None
    flysto_password: str | None
    flysto_web_base_url: str
    flysto_upload_url: str | None
    flysto_session_cookie: str | None
    flysto_log_upload_url: str | None
    flysto_include_metadata: bool
    flysto_api_version: str | None
    flysto_min_request_interval: float
    flysto_max_request_retries: int
    mode: str
    headless: bool
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
    mode = (_get_env("MODE") or "auto").lower()

    cloudahoy_email = _get_env("CLOUD_AHOY_EMAIL")
    cloudahoy_password = _get_env("CLOUD_AHOY_PASSWORD")
    flysto_email = _get_env("FLYSTO_EMAIL")
    flysto_password = _get_env("FLYSTO_PASSWORD")
    cloudahoy_api_key = _get_env("CLOUD_AHOY_API_KEY")
    flysto_api_key = _get_env("FLYSTO_API_KEY")
    flysto_session_cookie = _get_env("FLYSTO_SESSION_COOKIE")
    flysto_log_upload_url = _get_env("FLYSTO_LOG_UPLOAD_URL")
    flysto_api_version = _get_env("FLYSTO_API_VERSION")
    flysto_min_request_interval = _get_env("FLYSTO_MIN_REQUEST_INTERVAL")
    flysto_max_request_retries = _get_env("FLYSTO_MAX_REQUEST_RETRIES")

    if mode in {"api", "hybrid", "auto"}:
        missing = [
            name
            for name, value in (
                ("CLOUD_AHOY_EMAIL", cloudahoy_email),
                ("CLOUD_AHOY_PASSWORD", cloudahoy_password),
            )
            if value is None
        ]
        if missing:
            raise ConfigError(f"Missing required env vars: {', '.join(missing)}")

    cloudahoy_base_url = _get_env("CLOUD_AHOY_BASE_URL") or "https://www.cloudahoy.com/api"
    flysto_base_url = _get_env("FLYSTO_BASE_URL") or "https://www.flysto.net"
    cloudahoy_web_base_url = _get_env("CLOUD_AHOY_WEB_BASE_URL") or "https://www.cloudahoy.com"
    flysto_web_base_url = _get_env("FLYSTO_WEB_BASE_URL") or "https://www.flysto.net"
    cloudahoy_flights_url = _get_env("CLOUD_AHOY_FLIGHTS_URL")
    cloudahoy_export_url_template = _get_env("CLOUD_AHOY_EXPORT_URL_TEMPLATE")
    flysto_upload_url = _get_env("FLYSTO_UPLOAD_URL")
    include_metadata_value = (_get_env("FLYSTO_INCLUDE_METADATA") or "false").lower()
    flysto_include_metadata = include_metadata_value in {"1", "true", "yes", "on"}

    headless_value = (_get_env("BROWSER_HEADLESS") or "true").lower()
    headless = headless_value in {"1", "true", "yes", "on"}

    dry_run_value = (_get_env("DRY_RUN") or "false").lower()
    dry_run = dry_run_value in {"1", "true", "yes", "on"}

    max_flights_value = _get_env("MAX_FLIGHTS")
    max_flights = int(max_flights_value) if max_flights_value else None

    min_request_interval = (
        float(flysto_min_request_interval)
        if flysto_min_request_interval is not None
        else 0.1
    )
    max_request_retries = (
        int(flysto_max_request_retries)
        if flysto_max_request_retries is not None
        else 2
    )

    return Config(
        cloudahoy_api_key=cloudahoy_api_key,
        cloudahoy_base_url=cloudahoy_base_url,
        cloudahoy_email=cloudahoy_email,
        cloudahoy_password=cloudahoy_password,
        cloudahoy_web_base_url=cloudahoy_web_base_url,
        cloudahoy_flights_url=cloudahoy_flights_url,
        cloudahoy_export_url_template=cloudahoy_export_url_template,
        flysto_api_key=flysto_api_key,
        flysto_base_url=flysto_base_url,
        flysto_email=flysto_email,
        flysto_password=flysto_password,
        flysto_web_base_url=flysto_web_base_url,
        flysto_upload_url=flysto_upload_url,
        flysto_session_cookie=flysto_session_cookie,
        flysto_log_upload_url=flysto_log_upload_url,
        flysto_include_metadata=flysto_include_metadata,
        flysto_api_version=flysto_api_version,
        flysto_min_request_interval=min_request_interval,
        flysto_max_request_retries=max_request_retries,
        mode=mode,
        headless=headless,
        dry_run=dry_run,
        max_flights=max_flights,
    )
