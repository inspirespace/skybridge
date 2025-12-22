from __future__ import annotations

from dataclasses import dataclass

from src.models import FlightDetail


@dataclass(frozen=True)
class FlyStoClient:
    api_key: str
    base_url: str

    def upload_flight(self, flight: FlightDetail, dry_run: bool = False) -> None:
        """
        TODO: Implement FlySto upload API call.
        """
        if dry_run:
            return
        _ = flight
        raise NotImplementedError(
            "FlySto upload needs API docs (endpoint, auth, payload format)."
        )
