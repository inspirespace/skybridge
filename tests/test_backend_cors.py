from __future__ import annotations

from src.backend import cors


def test_resolve_cors_origins_prefers_explicit_env(monkeypatch) -> None:
    monkeypatch.setenv("CORS_ALLOW_ORIGINS", "https://one.example, https://two.example")
    monkeypatch.setenv("SKYBRIDGE_DEV_DOMAIN", "dev.example")
    monkeypatch.setattr(cors, "resolve_project_id", lambda: "demo-project")

    origins, origin_regex = cors.resolve_cors_origins()

    assert origins == ["https://one.example", "https://two.example"]
    assert origin_regex is None


def test_resolve_cors_origins_uses_dev_domain_when_explicit_is_missing(monkeypatch) -> None:
    monkeypatch.delenv("CORS_ALLOW_ORIGINS", raising=False)
    monkeypatch.setenv("SKYBRIDGE_DEV_DOMAIN", "https://local.dev.example/path")
    monkeypatch.setattr(cors, "resolve_project_id", lambda: "demo-project")

    origins, origin_regex = cors.resolve_cors_origins()

    assert origins == [
        "https://local.dev.example",
        "https://emulator.local.dev.example",
        "http://local.dev.example",
        "http://emulator.local.dev.example",
    ]
    assert origin_regex is None


def test_resolve_cors_origins_uses_project_domains(monkeypatch) -> None:
    monkeypatch.delenv("CORS_ALLOW_ORIGINS", raising=False)
    monkeypatch.delenv("SKYBRIDGE_DEV_DOMAIN", raising=False)
    monkeypatch.setattr(cors, "resolve_project_id", lambda: "demo-project")

    origins, origin_regex = cors.resolve_cors_origins()

    assert origins == [
        "https://demo-project.web.app",
        "https://demo-project.firebaseapp.com",
    ]
    assert origin_regex is None


def test_resolve_cors_origins_falls_back_to_loopback(monkeypatch) -> None:
    monkeypatch.delenv("CORS_ALLOW_ORIGINS", raising=False)
    monkeypatch.delenv("SKYBRIDGE_DEV_DOMAIN", raising=False)
    monkeypatch.setattr(cors, "resolve_project_id", lambda: None)

    origins, origin_regex = cors.resolve_cors_origins()

    assert origins == ["http://localhost"]
    assert origin_regex == r"^https?://(localhost|127\.0\.0\.1|\[::1\])(?::\d+)?$"


def test_select_allow_origin_echoes_matching_origin() -> None:
    allowed = ["https://app.example", "https://emulator.app.example"]

    resolved = cors.select_allow_origin("https://emulator.app.example", allowed, None)

    assert resolved == "https://emulator.app.example"


def test_select_allow_origin_accepts_regex_matches() -> None:
    allowed = ["http://localhost"]
    regex = r"^https?://(localhost|127\.0\.0\.1|\[::1\])(?::\d+)?$"

    resolved = cors.select_allow_origin("http://127.0.0.1:5173", allowed, regex)

    assert resolved == "http://127.0.0.1:5173"


def test_select_allow_origin_falls_back_to_first_origin_for_unknown_request() -> None:
    allowed = ["https://app.example", "https://emulator.app.example"]

    resolved = cors.select_allow_origin("https://unknown.example", allowed, None)

    assert resolved == "https://app.example"


def test_select_allow_origin_supports_wildcard() -> None:
    resolved = cors.select_allow_origin("https://any.example", ["*"], None)

    assert resolved == "*"
