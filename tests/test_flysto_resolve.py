from __future__ import annotations

import json

from src.core.flysto.client import FlyStoClient


class DummyResponse:
    def __init__(self, text: str, status_code: int = 200) -> None:
        self.text = text
        self.status_code = status_code


class DummyFlyStoResolve(FlyStoClient):
    def __init__(self) -> None:
        super().__init__(api_key="", base_url="https://example.test")
        self.calls: list[tuple[str, str]] = []

    def _ensure_session(self, session):
        return None

    def _request(self, session, method: str, url: str, **kwargs):
        self.calls.append((method.lower(), url))
        if url.endswith("/api/log-list"):
            return DummyResponse(text=json.dumps(["log-a", "log-b"]))
        if url.endswith("/api/log-summary"):
            payload = {
                "items": [
                    {
                        "id": "log-b",
                        "summary": {
                            "data": {
                                "t3": [{"file": "flight.g3x.csv", "format": "UnknownGarmin"}],
                                "6h": "SIGVALUE",
                            }
                        },
                    }
                ]
            }
            return DummyResponse(text=json.dumps(payload))
        return DummyResponse(text="{}")


def test_resolve_log_for_file_uses_log_summary():
    client = DummyFlyStoResolve()
    log_id, signature, log_format = client.resolve_log_for_file("flight.g3x.csv")
    assert log_id == "log-b"
    assert signature == "SIGVALUE"
    assert log_format == "UnknownGarmin"
