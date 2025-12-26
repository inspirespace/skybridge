from __future__ import annotations

from src.config import Config
from src.cli import run


class DummyClient:
    def __init__(self, *args, **kwargs) -> None:
        pass

    def prepare(self) -> bool:
        return True


def _fake_config() -> Config:
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
        mode="api",
        headless=True,
        dry_run=False,
        max_flights=None,
    )


def test_guided_ctrl_c_is_clean(monkeypatch, tmp_path, capsys):
    monkeypatch.setenv("RUNS_DIR", str(tmp_path))
    monkeypatch.delenv("RUN_ID", raising=False)
    monkeypatch.setattr("src.cli.load_config", lambda: _fake_config())
    monkeypatch.setattr("src.cli.CloudAhoyClient", DummyClient)
    monkeypatch.setattr("src.cli.FlyStoClient", DummyClient)

    import src.guided as guided_module

    def _raise_keyboard_interrupt(*args, **kwargs):
        raise KeyboardInterrupt

    monkeypatch.setattr(guided_module, "run_guided", _raise_keyboard_interrupt)

    exit_code = run(["--guided"])
    assert exit_code == 130
    out = capsys.readouterr().out
    assert "Guided run cancelled." in out
