from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from src.models import FlightDetail, FlightSummary


@dataclass(frozen=True)
class CloudAhoyClient:
    api_key: str
    base_url: str

    def list_flights(self, limit: int | None = None) -> list[FlightSummary]:
        """
        TODO: Implement CloudAhoy API call.
        Expected fields: flight id, start time, duration, aircraft type, tail number.
        """
        _ = limit
        return []

    def fetch_flight(self, flight_id: str) -> FlightDetail:
        """
        TODO: Implement CloudAhoy API call for detailed flight payload.
        """
        return FlightDetail(
            id=flight_id,
            raw_payload={
                "placeholder": True,
                "fetched_at": datetime.utcnow().isoformat(),
            },
        )
