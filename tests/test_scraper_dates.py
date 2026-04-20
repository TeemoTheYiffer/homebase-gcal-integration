"""Unit tests for the pure date helpers in scraper.py.

Network-touching paths (login, fetch_weeks) are excluded -- those need real
credentials and are exercised by the smoke runner instead.
"""

from datetime import date

import pytest

from homebase_sync.scraper import monday_of_week, weeks_to_scrape


@pytest.mark.parametrize(
    ("input_date", "expected_monday"),
    [
        (date(2026, 4, 13), date(2026, 4, 13)),  # Monday -> itself
        (date(2026, 4, 15), date(2026, 4, 13)),  # Wednesday
        (date(2026, 4, 19), date(2026, 4, 13)),  # Sunday (end of same week)
        (date(2026, 4, 20), date(2026, 4, 20)),  # next Monday
        (date(2026, 1, 1), date(2025, 12, 29)),  # year boundary
    ],
)
def test_monday_of_week(input_date: date, expected_monday: date) -> None:
    assert monday_of_week(input_date) == expected_monday


def test_weeks_to_scrape_default_returns_two_mondays() -> None:
    assert weeks_to_scrape(date(2026, 4, 15)) == [date(2026, 4, 13), date(2026, 4, 20)]


def test_weeks_to_scrape_count_respected() -> None:
    out = weeks_to_scrape(date(2026, 4, 13), count=4)
    assert out == [date(2026, 4, 13), date(2026, 4, 20), date(2026, 4, 27), date(2026, 5, 4)]


def test_weeks_to_scrape_rejects_zero_count() -> None:
    with pytest.raises(ValueError):
        weeks_to_scrape(date(2026, 4, 13), count=0)
