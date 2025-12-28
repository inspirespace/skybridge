from __future__ import annotations

import json

from src.flysto.client import FlyStoClient


class DummyResponse:
    def __init__(self, text: str, status_code: int = 200) -> None:
        self.text = text
        self.status_code = status_code


class DummyFlyStoUpdate(FlyStoClient):
    def __init__(self) -> None:
        super().__init__(api_key="", base_url="https://example.test")
        self.summary_calls: list[dict] = []
        self.list_calls = 0

    def _ensure_session(self, session):
        return None

    def _request(self, session, method: str, url: str, **kwargs):
        if url.endswith("/api/log-list"):
            self.list_calls += 1
            return DummyResponse(text=json.dumps(["log-a"]))
        if url.endswith("/api/log-summary"):
            params = kwargs.get("params", {})
            self.summary_calls.append(params)
            if params.get("update") == "true":
                payload = {
                    "items": [
                        {
                            "id": "log-a",
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
            return DummyResponse(text=json.dumps({"items": []}))
        return DummyResponse(text="{}")


def test_resolve_log_for_file_uses_update_true_after_empty():
    client = DummyFlyStoUpdate()
    log_id, signature, log_format = client.resolve_log_for_file("flight.g3x.csv", retries=1)
    assert log_id == "log-a"
    assert signature == "SIGVALUE"
    assert log_format == "UnknownGarmin"
    assert client.summary_calls[-1].get("update") == "true"
