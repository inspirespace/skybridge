from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse, PlainTextResponse

app = FastAPI(title="CloudAhoy Mock")

_RUN_DIR = Path(os.getenv("MOCK_RUN_DIR", "/app/data/runs/20251230T204121Z"))
_REVIEW_PATH = _RUN_DIR / "review.json"
_EXPORTS_DIR = _RUN_DIR / "cloudahoy_exports"


class _State:
    flights: list[dict[str, Any]] | None = None


STATE = _State()


def _load_review() -> list[dict[str, Any]]:
    if STATE.flights is not None:
        return STATE.flights
    if not _REVIEW_PATH.exists():
        STATE.flights = []
        return STATE.flights
    data = json.loads(_REVIEW_PATH.read_text())
    items = data.get("items", []) if isinstance(data, dict) else []
    flights: list[dict[str, Any]] = []
    for item in items:
        flight_id = item.get("flight_id")
        if not flight_id:
            continue
        started_at = item.get("started_at")
        try:
            started_dt = datetime.fromisoformat(started_at.replace("Z", "+00:00"))
        except Exception:
            started_dt = datetime.now(tz=timezone.utc)
        flights.append(
            {
                "key": flight_id,
                "fdID": flight_id,
                "gmtStart": int(started_dt.timestamp()),
                "adjTime": int(started_dt.timestamp()),
                "nSec": item.get("duration_seconds") or 0,
                "tailNumber": item.get("tail_number"),
                "aircraft": {"P": {"typeAircraft": item.get("aircraft_type")}},
            }
        )
    STATE.flights = flights
    return flights


def _cookie_html() -> str:
    return (
        '<html><head></head><body>'
        '<script>'
        'setCookie("SID3","mock-sid");'
        'setCookie("USER3","mock-user");'
        'setCookie("EMAIL3","mock-email");'
        '</script>'
        '</body></html>'
    )


@app.post("/api/signin.cgi")
async def signin(_: Request) -> PlainTextResponse:
    return PlainTextResponse(_cookie_html(), media_type="text/html")


@app.post("/api/t-flights.cgi")
async def list_flights(_: Request) -> JSONResponse:
    flights = _load_review()
    return JSONResponse({"flights": flights, "more": False})


@app.post("/api/t-debrief.cgi")
async def debrief(request: Request) -> JSONResponse:
    payload = await request.json()
    flight_id = payload.get("flight") if isinstance(payload, dict) else None
    if not flight_id:
        raise HTTPException(status_code=400, detail="Missing flight id")
    path = _EXPORTS_DIR / f"{flight_id}.cloudahoy.json"
    if not path.exists():
        raise HTTPException(status_code=404, detail="Flight not found")
    data = json.loads(path.read_text())
    return JSONResponse(data)


@app.get("/healthz")
async def health() -> dict[str, str]:
    return {"status": "ok", "run_dir": str(_RUN_DIR)}
