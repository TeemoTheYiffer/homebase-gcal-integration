"""Unit tests for the HTML -> Shift parser using the fixture in tests/fixtures/."""

from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from homebase_sync.parser import parse_week_html
from homebase_sync.time_utils import (
    TimeParseError,
    combine_with_date,
    parse_time_range,
    parse_time_token,
)

FIXTURE_DIR = Path(__file__).parent / "fixtures"
LA = ZoneInfo("America/Los_Angeles")
WEEK_START = date(2026, 4, 13)
EMPLOYEE = "Emilio Dominic Aguirre"


@pytest.fixture(scope="module")
def sample_row_html() -> str:
    return (FIXTURE_DIR / "sample_row.html").read_text(encoding="utf-8")


def test_parses_four_shifts_for_known_employee(sample_row_html: str) -> None:
    result = parse_week_html(sample_row_html, WEEK_START, [EMPLOYEE], LA)
    assert set(result) == {EMPLOYEE}
    assert len(result[EMPLOYEE]) == 4


def test_unknown_employee_present_with_empty_list(sample_row_html: str) -> None:
    result = parse_week_html(sample_row_html, WEEK_START, [EMPLOYEE, "Nobody Here"], LA)
    assert result["Nobody Here"] == []
    assert len(result[EMPLOYEE]) == 4


def test_shift_fields_match_fixture(sample_row_html: str) -> None:
    shifts = parse_week_html(sample_row_html, WEEK_START, [EMPLOYEE], LA)[EMPLOYEE]
    by_id = {s.shift_id: s for s in shifts}

    expected = {
        "2212648713": (
            date(2026, 4, 16),
            datetime(2026, 4, 16, 14, 0, tzinfo=LA),
            datetime(2026, 4, 16, 20, 0, tzinfo=LA),
        ),
        "2192445344": (
            date(2026, 4, 17),
            datetime(2026, 4, 17, 14, 0, tzinfo=LA),
            datetime(2026, 4, 17, 20, 0, tzinfo=LA),
        ),
        "2192445368": (
            date(2026, 4, 18),
            datetime(2026, 4, 18, 11, 0, tzinfo=LA),
            datetime(2026, 4, 18, 18, 0, tzinfo=LA),
        ),
        "2192445369": (
            date(2026, 4, 19),
            datetime(2026, 4, 19, 10, 0, tzinfo=LA),
            datetime(2026, 4, 19, 16, 0, tzinfo=LA),
        ),
    }
    assert set(by_id) == set(expected)
    for sid, (d, start, end) in expected.items():
        s = by_id[sid]
        assert s.shift_date == d
        assert s.start == start
        assert s.end == end
        assert s.role == "Prep/Fryer"


def test_gcal_event_id_format(sample_row_html: str) -> None:
    shifts = parse_week_html(sample_row_html, WEEK_START, [EMPLOYEE], LA)[EMPLOYEE]
    for s in shifts:
        assert s.gcal_event_id == f"homebase{s.shift_id}"
        assert s.gcal_event_id.isalnum() and s.gcal_event_id.islower()


# --- time_utils ---


@pytest.mark.parametrize(
    ("token", "expected_h", "expected_m"),
    [
        ("2pm", 14, 0),
        ("12pm", 12, 0),
        ("12am", 0, 0),
        ("11:30am", 11, 30),
        ("9PM", 21, 0),
    ],
)
def test_parse_time_token(token: str, expected_h: int, expected_m: int) -> None:
    t = parse_time_token(token)
    assert (t.hour, t.minute) == (expected_h, expected_m)


def test_parse_time_token_rejects_missing_meridiem() -> None:
    with pytest.raises(TimeParseError):
        parse_time_token("14:00")


def test_parse_time_range_basic() -> None:
    start, end = parse_time_range("11:30am-2pm")
    assert (start.hour, start.minute) == (11, 30)
    assert (end.hour, end.minute) == (14, 0)


def test_parse_time_range_overnight_via_combine() -> None:
    start_t, end_t = parse_time_range("9pm-1am")
    start_dt, end_dt = combine_with_date(date(2026, 4, 17), start_t, end_t, LA)
    assert start_dt == datetime(2026, 4, 17, 21, 0, tzinfo=LA)
    assert end_dt == datetime(2026, 4, 18, 1, 0, tzinfo=LA)
