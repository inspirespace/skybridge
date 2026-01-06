"""src/core/models.py module."""
from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class FlightSummary:
    """Represents FlightSummary."""
    id: str
    started_at: datetime
    duration_seconds: int | None
    aircraft_type: str | None
    tail_number: str | None
    cloudahoy_key: str | None = None
    fd_id: str | None = None


@dataclass(frozen=True)
class FlightDetail:
    """Represents FlightDetail."""
    id: str
    raw_payload: dict
    raw_path: str | None = None
    file_path: str | None = None
    file_type: str | None = None
    metadata_path: str | None = None
    csv_path: str | None = None
    export_paths: dict[str, str] | None = None


@dataclass(frozen=True)
class MigrationResult:
    """Represents MigrationResult."""
    flight_id: str
    status: str
    message: str | None = None
