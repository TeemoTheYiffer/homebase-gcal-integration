"""Convert rendered Homebase HTML into shifts grouped by employee."""

import logging
from collections.abc import Iterable
from datetime import date
from zoneinfo import ZoneInfo

from bs4 import BeautifulSoup, Tag

from .models import Shift
from .time_utils import combine_with_date, date_for_day_column, parse_time_range

logger = logging.getLogger("homebase_sync.parser")

_SHIFT_TESTID_PREFIX = "ShiftItem__"
_DAY_TESTIDS = ("monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday")


class ParseError(Exception):
    """Raised when expected DOM structure is missing for a shift tile."""


def parse_week_html(
    html: str,
    week_start: date,
    employee_names: Iterable[str],
    tz: ZoneInfo,
) -> dict[str, list[Shift]]:
    """Extract shifts for each named employee from a rendered weekly grid.

    Args:
        html: Full page HTML (post-render via Playwright).
        week_start: The Monday of the week shown in the grid.
        employee_names: Exact display names to pull rows for.
        tz: Timezone to attach to shift datetimes.

    Returns:
        Mapping of employee name -> shifts in DOM order (Mon->Sun). Names with
        no matching row appear with an empty list.
    """
    soup = BeautifulSoup(html, "lxml")
    name_set = {n.strip() for n in employee_names}
    rows_by_name = _index_employee_rows(soup, name_set)

    result: dict[str, list[Shift]] = {name: [] for name in name_set}
    for name, row in rows_by_name.items():
        result[name] = _shifts_from_row(row, week_start, tz)

    missing = name_set - rows_by_name.keys()
    for name in missing:
        logger.warning("no employee row found for %r", name)

    return result


def _index_employee_rows(soup: BeautifulSoup, wanted: set[str]) -> dict[str, Tag]:
    """One pass over the grid; pick out rows whose name matches the wanted set."""
    found: dict[str, Tag] = {}
    for row in soup.find_all("div", class_="EWVEmployeeRow"):
        if not isinstance(row, Tag):
            continue
        name_link = row.find("div", class_="employee-name-link")
        if name_link is None:
            continue
        name_p = name_link.find("p")
        if name_p is None:
            continue
        name = name_p.get_text(strip=True)
        if name in wanted:
            found[name] = row
    return found


def _shifts_from_row(row: Tag, week_start: date, tz: ZoneInfo) -> list[Shift]:
    shifts: list[Shift] = []
    for day_testid in _DAY_TESTIDS:
        day_cell = row.find("div", attrs={"data-testid": day_testid})
        if not isinstance(day_cell, Tag):
            continue
        shift_date = date_for_day_column(week_start, day_testid)
        for tile in day_cell.find_all("div", attrs={"data-testid": True}):
            testid = tile.get("data-testid", "")
            if not isinstance(testid, str) or not testid.startswith(_SHIFT_TESTID_PREFIX):
                continue
            shifts.append(_parse_shift_tile(tile, testid, shift_date, tz))
    return shifts


def _parse_shift_tile(tile: Tag, testid: str, shift_date: date, tz: ZoneInfo) -> Shift:
    shift_id = testid[len(_SHIFT_TESTID_PREFIX):]
    paragraphs = tile.find_all("p")
    if len(paragraphs) < 2:
        raise ParseError(f"shift tile {testid} has fewer than 2 <p> children")
    time_text = paragraphs[0].get_text(strip=True)
    role_text = paragraphs[1].get_text(strip=True)

    start_t, end_t = parse_time_range(time_text)
    start_dt, end_dt = combine_with_date(shift_date, start_t, end_t, tz)
    return Shift(
        shift_id=shift_id,
        shift_date=shift_date,
        start=start_dt,
        end=end_dt,
        role=role_text,
    )
