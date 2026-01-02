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

_RUN_DIR = Path(os.getenv("MOCK_RUN_DIR", "/app/tests/fixtures/run-20251228T185601Z"))
_REVIEW_PATH = _RUN_DIR / "review.json"


class _State:
    flights: list[dict[str, Any]] | None = None
    items_by_id: dict[str, dict[str, Any]] | None = None


STATE = _State()


def _load_review() -> list[dict[str, Any]]:
    if STATE.flights is not None:
        return STATE.flights
    if not _REVIEW_PATH.exists():
        STATE.flights = []
        return STATE.flights
    data = json.loads(_REVIEW_PATH.read_text())
    items = data.get("items", []) if isinstance(data, dict) else []
    STATE.items_by_id = {
        item.get("flight_id"): item for item in items if isinstance(item, dict)
    }
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


def _load_item(flight_id: str) -> dict[str, Any] | None:
    if STATE.items_by_id is None:
        _load_review()
    if STATE.items_by_id is None:
        return None
    return STATE.items_by_id.get(flight_id)


def _build_points(item: dict[str, Any]) -> list[list[Any]]:
    points_preview = item.get("points_preview")
    if not isinstance(points_preview, list) or not points_preview:
        return []
    schema = item.get("points_schema")
    names: list[str] = []
    if isinstance(schema, list):
        ordered = sorted(
            [entry for entry in schema if isinstance(entry, dict)],
            key=lambda entry: entry.get("index", 0),
        )
        names = [entry.get("name") for entry in ordered if entry.get("name")]
    if not names and isinstance(points_preview[0], dict):
        names = list(points_preview[0].keys())
    points: list[list[Any]] = []
    for entry in points_preview:
        if not isinstance(entry, dict):
            continue
        points.append([entry.get(name) for name in names])
    return points


def _build_meta(item: dict[str, Any]) -> dict[str, Any]:
    meta: dict[str, Any] = {}
    metadata = item.get("metadata")
    if isinstance(metadata, dict):
        meta.update(metadata)
    if "tailNumber" not in meta and item.get("tail_number"):
        meta["tailNumber"] = item.get("tail_number")
    if "summary" not in meta and isinstance(metadata, dict) and metadata.get("summary"):
        meta["summary"] = metadata.get("summary")
    return meta


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
    item = _load_item(flight_id)
    if not item:
        raise HTTPException(status_code=404, detail="Flight not found")
    data = {
        "flt": {
            "points": _build_points(item),
            "Meta": _build_meta(item),
            "p": {},
        }
    }
    return JSONResponse(data)


@app.get("/healthz")
async def health() -> dict[str, str]:
    return {"status": "ok", "run_dir": str(_RUN_DIR)}
