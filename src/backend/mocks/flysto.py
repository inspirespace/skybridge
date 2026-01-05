"""src/backend/mocks/flysto.py module."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse

app = FastAPI(title="FlySto Mock")

_RUN_DIR = Path(os.getenv("MOCK_RUN_DIR", "/app/data/runs/20251230T204121Z"))
_IMPORT_REPORT = _RUN_DIR / "import_report.json"


class _State:
    uploads: dict[str, dict[str, str]] = {}
    aircraft: list[dict[str, Any]] = []
    crew: list[dict[str, Any]] = []


STATE = _State()


def _make_log_id(filename: str) -> str:
    """Internal helper for make log id."""
    digest = hashlib.sha1(filename.encode("utf-8")).hexdigest()[:10]
    return f"mock-{digest}"


def _ensure_upload(filename: str) -> dict[str, str]:
    """Internal helper for ensure upload."""
    existing = STATE.uploads.get(filename)
    if existing:
        return existing
    log_id = _make_log_id(filename)
    signature = f"{filename}/sig/{log_id}"
    log_format = "gpx"
    payload = {"log_id": log_id, "signature": signature, "log_format": log_format}
    STATE.uploads[filename] = payload
    return payload


@app.post("/api/login")
async def login(_: Request) -> JSONResponse:
    """Handle login."""
    response = JSONResponse({"status": "ok"})
    response.set_cookie("USER_SESSION", "mock-session", path="/")
    return response


@app.post("/api/log-upload")
async def log_upload(request: Request) -> JSONResponse:
    """Handle log upload."""
    query = parse_qs(request.url.query)
    raw_id = query.get("id", [""])[0]
    filename = raw_id.split("@@@")[0] if raw_id else "upload.zip"
    data = _ensure_upload(filename)
    return JSONResponse({"signature": data["signature"], "logId": data["log_id"], "logFormat": data["log_format"]})


@app.get("/api/log-list")
async def log_list() -> JSONResponse:
    """Handle log list."""
    log_ids = [entry["log_id"] for entry in STATE.uploads.values()]
    return JSONResponse(log_ids)


@app.get("/api/log-summary")
async def log_summary() -> JSONResponse:
    """Handle log summary."""
    items = []
    for filename, entry in STATE.uploads.items():
        items.append(
            {
                "id": entry["log_id"],
                "summary": {
                    "data": {
                        "t3": [{"file": filename, "format": entry["log_format"]}],
                        "6h": entry["signature"],
                    }
                },
            }
        )
    return JSONResponse({"items": items})


@app.get("/api/log-metadata")
async def log_metadata(request: Request) -> JSONResponse:
    """Handle log metadata."""
    params = request.query_params
    log_id = params.get("logIdString") or params.get("log") or params.get("logId")
    items = []
    if log_id:
        items.append({"id": str(log_id), "aircraft": 0})
    return JSONResponse(
        {
            "items": items,
            "aircraft": [
                {"avionics": {"logFormatId": "gpx", "systemId": "mock-system"}}
            ],
        }
    )


@app.post("/api/assign-aircraft")
async def assign_aircraft(_: Request) -> JSONResponse:
    """Handle assign aircraft."""
    return JSONResponse({"status": "ok"})


@app.post("/api/assign-crew")
async def assign_crew(_: Request) -> JSONResponse:
    """Handle assign crew."""
    return JSONResponse({"status": "ok"})


@app.put("/api/log-annotations/{log_id}")
@app.post("/api/log-annotations/{log_id}")
async def log_annotations(log_id: str, _: Request) -> JSONResponse:
    """Handle log annotations."""
    return JSONResponse({"status": "ok", "logId": log_id})


@app.get("/api/aircraft-profiles")
async def aircraft_profiles() -> JSONResponse:
    """Handle aircraft profiles."""
    return JSONResponse([{"modelId": "Other", "modelName": "Other"}])


@app.get("/api/aircraft")
async def aircraft() -> JSONResponse:
    """Handle aircraft."""
    return JSONResponse(STATE.aircraft)


@app.post("/api/create-aircraft")
async def create_aircraft(request: Request) -> JSONResponse:
    """Create aircraft."""
    payload = await request.json()
    tail = payload.get("tailNumber") or payload.get("tail-number")
    entry = {"id": f"ac-{len(STATE.aircraft)+1}", "tail-number": tail}
    STATE.aircraft.append(entry)
    return JSONResponse(entry)


@app.get("/api/user-crew-roles")
async def crew_roles() -> JSONResponse:
    """Handle crew roles."""
    return JSONResponse(
        [
            {"id": "1", "name": "Pilot in command"},
            {"id": "2", "name": "Pilot"},
            {"id": "3", "name": "Copilot"},
        ]
    )


@app.get("/api/user-crew")
async def user_crew() -> JSONResponse:
    """Handle user crew."""
    return JSONResponse(STATE.crew)


@app.get("/api/crew")
async def crew() -> JSONResponse:
    """Handle crew."""
    return JSONResponse(STATE.crew)


@app.post("/api/new-crew")
async def new_crew(request: Request) -> JSONResponse:
    """Handle new crew."""
    payload = await request.json()
    name = payload.get("name") if isinstance(payload, dict) else None
    if not name:
        raise HTTPException(status_code=400, detail="Missing crew name")
    entry = {"id": f"crew-{len(STATE.crew)+1}", "name": name}
    STATE.crew.append(entry)
    return JSONResponse(entry)


@app.get("/api/log-files-to-process")
async def log_files_to_process() -> JSONResponse:
    """Handle log files to process."""
    return JSONResponse({"nFiles": 0})


@app.get("/healthz")
async def health() -> dict[str, str]:
    """Handle health."""
    return {"status": "ok", "run_dir": str(_RUN_DIR)}
