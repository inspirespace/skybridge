from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class FlightSummary:
    id: str
    started_at: datetime
    duration_seconds: int | None
    aircraft_type: str | None
    tail_number: str | None


@dataclass(frozen=True)
class FlightDetail:
    id: str
    raw_payload: dict
    file_path: str | None = None
    file_type: str | None = None
    metadata_path: str | None = None
    csv_path: str | None = None


@dataclass(frozen=True)
class MigrationResult:
    flight_id: str
    status: str
    message: str | None = None
