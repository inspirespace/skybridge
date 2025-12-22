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


@dataclass(frozen=True)
class MigrationResult:
    flight_id: str
    status: str
    message: str | None = None
