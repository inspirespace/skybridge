"""Tests for FlySto web helpers."""
from __future__ import annotations

from pathlib import Path

import pytest

from src.core.models import FlightDetail
from src.core.web.flysto import FlyStoWebClient, FlyStoWebConfig


class DummyLocator:
    def __init__(self, count=0, on_click=None, on_set_files=None):
        self._count = count
        self._on_click = on_click
        self._on_set_files = on_set_files
        self.first = self

    def count(self):
        return self._count

    def fill(self, *_args, **_kwargs):
        return None

    def click(self):
        if self._on_click:
            self._on_click()
        return None

    def set_input_files(self, *_args, **_kwargs):
        if self._on_set_files:
            self._on_set_files()
        return None


class DummyPage:
    def __init__(
        self,
        email_present=True,
        password_present=True,
        file_inputs=0,
        upload_trigger=False,
        browse_files=False,
        submit_button=False,
    ):
        self._email_present = email_present
        self._password_present = password_present
        self._file_inputs = file_inputs
        self._upload_trigger = upload_trigger
        self._browse_files = browse_files
        self._submit_button = submit_button
        self.last_url = None
        self.files_set = False

    def goto(self, *_args, **_kwargs):
        if _args:
            self.last_url = _args[0]
        return None

    def locator(self, selector: str):
        if "email" in selector:
            return DummyLocator(count=1 if self._email_present else 0)
        if "password" in selector:
            return DummyLocator(count=1 if self._password_present else 0)
        if "input[type=file]" in selector:
            return DummyLocator(count=self._file_inputs, on_set_files=self.set_files)
        return DummyLocator(count=0)

    def get_by_text(self, _label: str):
        if _label == "Browse files" and self._browse_files:
            return DummyLocator(count=1, on_click=self._open_file_input)
        if _label in {"Load logs", "Upload", "Add flight", "Import", "Upload flight"} and self._upload_trigger:
            return DummyLocator(count=1, on_click=self._open_file_input)
        if _label in {"Upload", "Import", "Submit", "Save"} and self._submit_button:
            return DummyLocator(count=1)
        return DummyLocator(count=0)

    class keyboard:
        @staticmethod
        def press(_key: str):
            return None

    def wait_for_load_state(self, *_args, **_kwargs):
        return None

    def wait_for_timeout(self, *_args, **_kwargs):
        return None

    def _open_file_input(self):
        self._file_inputs = 1

    def set_files(self):
        self.files_set = True


def _config(tmp_path: Path) -> FlyStoWebConfig:
    return FlyStoWebConfig(
        base_url="https://flysto",
        email=None,
        password=None,
        upload_url=None,
        storage_state_path=tmp_path / "state.json",
        headless=True,
    )


def test_ensure_login_requires_creds(tmp_path: Path) -> None:
    client = FlyStoWebClient(_config(tmp_path))
    with pytest.raises(RuntimeError):
        client._ensure_login(DummyPage(email_present=True, password_present=True))


def test_ensure_login_skips_when_no_email(tmp_path: Path) -> None:
    client = FlyStoWebClient(_config(tmp_path))
    client._ensure_login(DummyPage(email_present=False, password_present=False))


def test_ensure_login_missing_password_raises(tmp_path: Path) -> None:
    config = FlyStoWebConfig(
        base_url="https://flysto",
        email="user",
        password="secret",
        upload_url=None,
        storage_state_path=tmp_path / "state.json",
        headless=True,
    )
    client = FlyStoWebClient(config)
    with pytest.raises(RuntimeError):
        client._ensure_login(DummyPage(email_present=True, password_present=False))


def test_navigate_to_upload_with_explicit_url(tmp_path: Path) -> None:
    config = _config(tmp_path)
    config = FlyStoWebConfig(
        base_url=config.base_url,
        email=None,
        password=None,
        upload_url="https://flysto/upload",
        storage_state_path=config.storage_state_path,
        headless=True,
    )
    client = FlyStoWebClient(config)
    page = DummyPage()
    client._navigate_to_upload(page)
    assert page.last_url == "https://flysto/upload"


def test_navigate_to_upload_clicks_trigger(tmp_path: Path) -> None:
    client = FlyStoWebClient(_config(tmp_path))
    page = DummyPage(upload_trigger=True, file_inputs=0)
    client._navigate_to_upload(page)
    assert page._file_inputs == 1


def test_navigate_to_upload_requires_trigger(tmp_path: Path) -> None:
    client = FlyStoWebClient(_config(tmp_path))
    with pytest.raises(RuntimeError):
        client._navigate_to_upload(DummyPage(upload_trigger=False))


def test_upload_file_requires_input(tmp_path: Path) -> None:
    client = FlyStoWebClient(_config(tmp_path))
    with pytest.raises(RuntimeError):
        client._upload_file(DummyPage(file_inputs=0), tmp_path / "file.gpx")


def test_upload_file_uses_browse_files(tmp_path: Path) -> None:
    client = FlyStoWebClient(_config(tmp_path))
    page = DummyPage(file_inputs=0, browse_files=True, submit_button=True)
    client._upload_file(page, tmp_path / "file.gpx")
    assert page.files_set is True


def test_upload_flight_requires_path(tmp_path: Path) -> None:
    client = FlyStoWebClient(_config(tmp_path))
    with pytest.raises(RuntimeError):
        client.upload_flight(FlightDetail(id="f1", raw_payload={}))
