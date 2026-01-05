from __future__ import annotations

from src.core.config import Config, ConfigError
from src.core.cli import run


class DummyClient:
    def __init__(self, *args, **kwargs) -> None:
    """Internal helper for init  ."""
        pass

    def prepare(self) -> bool:
    """Handle prepare."""
        return True


def _fake_config() -> Config:
"""Internal helper for fake config."""
    return Config(
        cloudahoy_api_key=None,
        cloudahoy_base_url="https://example.com/api",
        cloudahoy_email="user@example.com",
        cloudahoy_password="secret",
        cloudahoy_web_base_url="https://example.com",
        cloudahoy_flights_url=None,
        cloudahoy_export_url_template=None,
        flysto_api_key=None,
        flysto_base_url="https://example.com",
        flysto_email="user@example.com",
        flysto_password="secret",
        flysto_web_base_url="https://example.com",
        flysto_upload_url=None,
        flysto_session_cookie=None,
        flysto_log_upload_url=None,
        flysto_include_metadata=False,
        flysto_api_version=None,
        flysto_min_request_interval=0.1,
        flysto_max_request_retries=2,
        cloudahoy_export_format="gpx",
        cloudahoy_export_formats=["g3x", "gpx"],
        mode="api",
        headless=True,
        dry_run=False,
        max_flights=None,
    )


def test_guided_ctrl_c_is_clean(monkeypatch, tmp_path, capsys):
"""Test guided ctrl c is clean."""
    monkeypatch.setenv("RUNS_DIR", str(tmp_path))
    monkeypatch.delenv("RUN_ID", raising=False)
    monkeypatch.setattr("src.core.cli.load_config", lambda: _fake_config())
    monkeypatch.setattr("src.core.cli.CloudAhoyClient", DummyClient)
    monkeypatch.setattr("src.core.cli.FlyStoClient", DummyClient)

    import src.core.guided as guided_module

    def _raise_keyboard_interrupt(*args, **kwargs):
    """Internal helper for raise keyboard interrupt."""
        raise KeyboardInterrupt

    monkeypatch.setattr(guided_module, "run_guided", _raise_keyboard_interrupt)

    exit_code = run(["--guided"])
    assert exit_code == 130
    out = capsys.readouterr().out
    assert "Guided run cancelled." in out


def test_guided_prompts_for_missing_env(monkeypatch, tmp_path):
"""Test guided prompts for missing env."""
    monkeypatch.setenv("RUNS_DIR", str(tmp_path))
    monkeypatch.delenv("RUN_ID", raising=False)
    calls = {"count": 0}

    def _load_config():
    """Internal helper for load config."""
        calls["count"] += 1
        if calls["count"] == 1:
            raise ConfigError(
                "Missing required env vars: CLOUD_AHOY_EMAIL, CLOUD_AHOY_PASSWORD"
            )
        return _fake_config()

    monkeypatch.setattr("src.core.cli.load_config", _load_config)
    monkeypatch.setattr("src.core.cli.CloudAhoyClient", DummyClient)
    monkeypatch.setattr("src.core.cli.FlyStoClient", DummyClient)
    monkeypatch.setattr("builtins.input", lambda prompt="": "user@example.com")
    monkeypatch.setattr("src.core.cli.getpass.getpass", lambda prompt="": "secret")

    import src.core.guided as guided_module

    monkeypatch.setattr(guided_module, "run_guided", lambda **kwargs: 0)

    exit_code = run(["--guided"])
    assert exit_code == 0
    assert calls["count"] >= 2
