"""tests/test_backend_mocks.py module."""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import src.backend.mocks.cloudahoy as cloudahoy_mock
import src.backend.mocks.flysto as flysto_mock


@pytest.fixture(autouse=True)
def reset_mock_state():
    cloudahoy_mock.STATE.flights = None
    cloudahoy_mock.STATE.items_by_id = None
    flysto_mock.STATE.uploads = {}
    flysto_mock.STATE.aircraft = []
    flysto_mock.STATE.crew = []
    flysto_mock.STATE.annotations = {}
    yield
    cloudahoy_mock.STATE.flights = None
    cloudahoy_mock.STATE.items_by_id = None


def test_cloudahoy_load_review_and_builders(tmp_path, monkeypatch):
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    review_path = run_dir / "review.json"
    review_payload = {
        "items": [
            {
                "flight_id": "F1",
                "started_at": "2025-01-01T00:00:00Z",
                "duration_seconds": 120,
                "tail_number": "N1",
                "aircraft_type": "C172",
                "points_preview": [
                    {"longitude_deg": -122.0, "latitude_deg": 47.0},
                    {"longitude_deg": -122.1, "latitude_deg": 47.1},
                ],
                "points_schema": [
                    {"index": 0, "name": "longitude_deg"},
                    {"index": 1, "name": "latitude_deg"},
                ],
                "metadata": {
                    "event_from": {"c": "KPAE"},
                    "event_to": {"t": "Paine Field"},
                },
            }
        ]
    }
    review_path.write_text(json.dumps(review_payload))

    monkeypatch.setattr(cloudahoy_mock, "_RUN_DIR", run_dir)
    monkeypatch.setattr(cloudahoy_mock, "_REVIEW_PATH", review_path)

    flights = cloudahoy_mock._load_review()
    assert flights
    assert flights[0]["fdID"] == "F1"

    item = cloudahoy_mock._load_item("F1")
    points = cloudahoy_mock._build_points(item)
    assert points == [[-122.0, 47.0], [-122.1, 47.1]]

    meta = cloudahoy_mock._build_meta(item)
    assert meta["from"] == "KPAE"
    assert meta["to"] == "Paine Field"
    assert meta["origin"] == "KPAE"


def test_cloudahoy_endpoints(tmp_path, monkeypatch):
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    review_path = run_dir / "review.json"
    review_path.write_text(
        json.dumps(
            {
                "items": [
                    {
                        "flight_id": "F2",
                        "started_at": "2025-01-02T00:00:00Z",
                        "duration_seconds": 60,
                    }
                ]
            }
        )
    )

    monkeypatch.setattr(cloudahoy_mock, "_RUN_DIR", run_dir)
    monkeypatch.setattr(cloudahoy_mock, "_REVIEW_PATH", review_path)

    client = TestClient(cloudahoy_mock.app)
    list_response = client.post("/api/t-flights.cgi")
    assert list_response.status_code == 200
    assert list_response.json()["flights"]

    debrief = client.post("/api/t-debrief.cgi", json={"flight": "F2"})
    assert debrief.status_code == 200
    assert "flt" in debrief.json()

    missing = client.post("/api/t-debrief.cgi", json={})
    assert missing.status_code == 400


def test_flysto_endpoints_and_state():
    client = TestClient(flysto_mock.app)

    login = client.post("/api/login")
    assert login.status_code == 200
    assert login.cookies.get("USER_SESSION") == "mock-session"

    upload = client.post("/api/log-upload?id=flight.csv@@@123")
    assert upload.status_code == 200
    payload = upload.json()
    assert payload["logId"].startswith("mock-")

    log_list = client.get("/api/log-list")
    assert payload["logId"] in log_list.json()

    summary = client.get("/api/log-summary")
    assert summary.json()["items"]

    annotations = client.post(f"/api/log-annotations/{payload['logId']}", json={"remarks": "ok", "tags": ["t1"]})
    assert annotations.status_code == 200

    metadata = client.get(f"/api/log-metadata?logIdString={payload['logId']}")
    assert metadata.json()["items"][0]["annotations"]["remarks"] == "ok"


def test_flysto_aircraft_and_crew():
    client = TestClient(flysto_mock.app)

    aircraft = client.post("/api/create-aircraft", json={"tailNumber": "N123"})
    assert aircraft.status_code == 200
    assert client.get("/api/aircraft").json()

    crew_missing = client.post("/api/new-crew", json={})
    assert crew_missing.status_code == 400

    crew = client.post("/api/new-crew", json={"name": "Pilot"})
    assert crew.status_code == 200
    assert client.get("/api/crew").json()

    assign = client.post(
        "/api/assign-crew",
        json={"logIds": ["log-1"], "names": ["Pilot"], "roles": ["PIC"]},
    )
    assert assign.status_code == 200
