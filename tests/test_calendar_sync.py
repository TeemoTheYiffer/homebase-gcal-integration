"""Unit tests for pure helpers in calendar_sync + config.

The Google API call sites (load_credentials, _upsert_shift, _delete_stale_events,
sync_all) are not exercised here -- they require either a real network round-trip
or non-trivial mocking of googleapiclient. The smoke runner covers them end-to-end.
"""

import json
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from homebase_sync.calendar_sync import build_event_body, sync_window
from homebase_sync.config import ConfigError, load_config
from homebase_sync.models import Shift

LA = ZoneInfo("America/Los_Angeles")
EMPLOYEE = "Emilio Dominic Aguirre"


@pytest.fixture
def shift() -> Shift:
    return Shift(
        shift_id="2192445344",
        shift_date=date(2026, 4, 17),
        start=datetime(2026, 4, 17, 14, 0, tzinfo=LA),
        end=datetime(2026, 4, 17, 20, 0, tzinfo=LA),
        role="Prep/Fryer",
    )


def test_event_body_uses_deterministic_id(shift: Shift) -> None:
    body = build_event_body(shift, EMPLOYEE, "America/Los_Angeles")
    assert body["id"] == "homebase2192445344"


def test_event_body_summary_and_description(shift: Shift) -> None:
    body = build_event_body(shift, EMPLOYEE, "America/Los_Angeles")
    assert body["summary"] == "Emilio Work: Prep/Fryer"
    assert "2192445344" in body["description"]
    assert EMPLOYEE in body["description"]


def test_event_body_summary_uses_first_token_of_name() -> None:
    from datetime import date, datetime

    s = Shift(
        shift_id="1",
        shift_date=date(2026, 4, 17),
        start=datetime(2026, 4, 17, 14, 0, tzinfo=LA),
        end=datetime(2026, 4, 17, 20, 0, tzinfo=LA),
        role="Prep/Fryer",
    )
    body = build_event_body(s, "Josiah Cyphers", "America/Los_Angeles")
    assert body["summary"] == "Josiah Work: Prep/Fryer"


def test_event_body_times_are_iso_with_offset(shift: Shift) -> None:
    body = build_event_body(shift, EMPLOYEE, "America/Los_Angeles")
    assert body["start"]["dateTime"] == "2026-04-17T14:00:00-07:00"
    assert body["end"]["dateTime"] == "2026-04-17T20:00:00-07:00"
    assert body["start"]["timeZone"] == "America/Los_Angeles"
    assert body["end"]["timeZone"] == "America/Los_Angeles"


def test_event_body_source_url_points_to_monday_of_week(shift: Shift) -> None:
    # Friday 2026-04-17 -- Monday of that week is 2026-04-13.
    body = build_event_body(shift, EMPLOYEE, "America/Los_Angeles")
    assert body["source"]["url"].endswith("/2026-04-13")


def test_sync_window_spans_listed_weeks() -> None:
    start, end = sync_window([date(2026, 4, 13), date(2026, 4, 20)], LA)
    assert start == datetime(2026, 4, 13, 0, 0, tzinfo=LA)
    assert end == datetime(2026, 4, 27, 0, 0, tzinfo=LA)  # Mon Apr 20 + 7 days


def test_sync_window_single_week() -> None:
    start, end = sync_window([date(2026, 4, 13)], LA)
    assert start == datetime(2026, 4, 13, 0, 0, tzinfo=LA)
    assert end == datetime(2026, 4, 20, 0, 0, tzinfo=LA)


def test_sync_window_dedupes_and_sorts() -> None:
    start, end = sync_window(
        [date(2026, 4, 20), date(2026, 4, 13), date(2026, 4, 13)], LA
    )
    assert start == datetime(2026, 4, 13, 0, 0, tzinfo=LA)
    assert end == datetime(2026, 4, 27, 0, 0, tzinfo=LA)


def test_sync_window_empty_raises() -> None:
    with pytest.raises(ValueError):
        sync_window([], LA)


# --- config: env-var content overrides ---


@pytest.fixture
def _isolated_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Strip any ambient .env-loaded vars and chdir to a clean tmp dir."""
    for key in (
        "HOMEBASE_EMAIL",
        "HOMEBASE_PASSWORD",
        "EMPLOYEES_CONFIG_PATH",
        "EMPLOYEES_CONFIG_TOML",
        "GCAL_CREDENTIALS_PATH",
        "GCAL_TOKEN_PATH",
        "GCAL_CREDENTIALS_JSON",
        "GCAL_TOKEN_JSON",
        "SYNC_TIMEZONE",
        "LOG_LEVEL",
    ):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.chdir(tmp_path)


def test_load_config_inline_employees_toml(
    monkeypatch: pytest.MonkeyPatch, _isolated_env: None
) -> None:
    monkeypatch.setenv("HOMEBASE_EMAIL", "x@y.com")
    monkeypatch.setenv("HOMEBASE_PASSWORD", "pw")
    monkeypatch.setenv(
        "EMPLOYEES_CONFIG_TOML",
        '[[employees]]\nname = "Alice"\ncalendar_id = "a@group.calendar.google.com"\n',
    )
    cfg = load_config()
    assert cfg.employees[0].name == "Alice"
    assert cfg.calendar_for("Alice") == "a@group.calendar.google.com"


def test_load_config_inline_credentials_and_token_dicts(
    monkeypatch: pytest.MonkeyPatch, _isolated_env: None
) -> None:
    monkeypatch.setenv("HOMEBASE_EMAIL", "x@y.com")
    monkeypatch.setenv("HOMEBASE_PASSWORD", "pw")
    monkeypatch.setenv(
        "EMPLOYEES_CONFIG_TOML",
        '[[employees]]\nname = "Alice"\ncalendar_id = "a@group.calendar.google.com"\n',
    )
    monkeypatch.setenv("GCAL_CREDENTIALS_JSON", json.dumps({"installed": {"client_id": "abc"}}))
    monkeypatch.setenv("GCAL_TOKEN_JSON", json.dumps({"refresh_token": "xyz"}))
    cfg = load_config()
    assert cfg.gcal_credentials_data == {"installed": {"client_id": "abc"}}
    assert cfg.gcal_token_data == {"refresh_token": "xyz"}


def test_load_config_invalid_json_env_raises(
    monkeypatch: pytest.MonkeyPatch, _isolated_env: None
) -> None:
    monkeypatch.setenv("HOMEBASE_EMAIL", "x@y.com")
    monkeypatch.setenv("HOMEBASE_PASSWORD", "pw")
    monkeypatch.setenv(
        "EMPLOYEES_CONFIG_TOML",
        '[[employees]]\nname = "Alice"\ncalendar_id = "a@group.calendar.google.com"\n',
    )
    monkeypatch.setenv("GCAL_CREDENTIALS_JSON", "not-json{")
    with pytest.raises(ConfigError, match="GCAL_CREDENTIALS_JSON is not valid JSON"):
        load_config()
