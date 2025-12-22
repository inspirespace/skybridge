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
        raise NotImplementedError(
            "CloudAhoy list_flights needs API docs (endpoint, auth, pagination)."
        )

    def fetch_flight(self, flight_id: str) -> FlightDetail:
        """
        TODO: Implement CloudAhoy API call for detailed flight payload.
        """
        _ = flight_id
        raise NotImplementedError(
            "CloudAhoy fetch_flight needs API docs (endpoint, export format)."
        )
