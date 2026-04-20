"""Time-string parsing and week-date math for Homebase shifts.

We deliberately avoid regex here -- the Homebase time format is small and
well-bounded, so plain string operations are easier to read and debug.
"""

from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

# Day column ordering on the Homebase weekly grid (Monday is column 0).
_DAY_OFFSETS: dict[str, int] = {
    "monday": 0,
    "tuesday": 1,
    "wednesday": 2,
    "thursday": 3,
    "friday": 4,
    "saturday": 5,
    "sunday": 6,
}


class TimeParseError(ValueError):
    """Raised when a Homebase time-range string can't be parsed."""


def parse_time_token(token: str) -> time:
    """Parse a single Homebase time token like ``"2pm"``, ``"11:30am"``, ``"12am"``.

    Args:
        token: A clock token ending in ``am`` or ``pm`` (case-insensitive).
            The hour portion may include ``:MM`` minutes.

    Returns:
        A ``datetime.time`` with the 24-hour equivalent.

    Raises:
        TimeParseError: If the token doesn't end with am/pm or has malformed
            hour/minute components.
    """
    cleaned = token.strip().lower()
    if cleaned.endswith("am"):
        is_pm = False
    elif cleaned.endswith("pm"):
        is_pm = True
    else:
        raise TimeParseError(f"time token must end with am/pm: {token!r}")

    body = cleaned[:-2].strip()
    if ":" in body:
        hour_str, minute_str = body.split(":", 1)
    else:
        hour_str, minute_str = body, "0"

    try:
        hour = int(hour_str)
        minute = int(minute_str)
    except ValueError as exc:
        raise TimeParseError(f"non-numeric hour/minute in {token!r}") from exc

    if not (1 <= hour <= 12) or not (0 <= minute <= 59):
        raise TimeParseError(f"hour/minute out of range in {token!r}")

    # 12am = 00:xx, 12pm = 12:xx, otherwise add 12 for pm.
    # The auto-suggested ternary collapse is unreadable; keeping the if/else.
    if hour == 12:  # noqa: SIM108
        hour_24 = 12 if is_pm else 0
    else:
        hour_24 = hour + 12 if is_pm else hour

    return time(hour=hour_24, minute=minute)


def parse_time_range(text: str) -> tuple[time, time]:
    """Parse a Homebase shift time range like ``"2pm-8pm"`` or ``"11:30am-2pm"``.

    Args:
        text: A range with two am/pm tokens separated by a single ``-``.

    Returns:
        Tuple ``(start_time, end_time)`` as naive ``datetime.time`` objects.

    Raises:
        TimeParseError: If the input doesn't contain exactly one ``-`` or
            either side fails to parse.
    """
    parts = text.split("-")
    if len(parts) != 2:
        raise TimeParseError(f"expected exactly one '-' in {text!r}")
    start_token, end_token = parts
    return parse_time_token(start_token), parse_time_token(end_token)


def combine_with_date(
    shift_date: date,
    start_t: time,
    end_t: time,
    tz: ZoneInfo,
) -> tuple[datetime, datetime]:
    """Attach date + timezone to start/end times, rolling end past midnight if needed.

    A shift like ``"9pm-1am"`` ends on the following calendar day. We detect this
    when ``end_t <= start_t`` and add one day to the end.
    """
    start_dt = datetime.combine(shift_date, start_t, tzinfo=tz)
    end_date = shift_date + timedelta(days=1) if end_t <= start_t else shift_date
    end_dt = datetime.combine(end_date, end_t, tzinfo=tz)
    return start_dt, end_dt


def date_for_day_column(week_start: date, day_testid: str) -> date:
    """Map a ``data-testid`` like ``"thursday"`` to a date in the given week.

    Args:
        week_start: The Monday of the week shown in the grid.
        day_testid: One of ``monday`` ... ``sunday`` (case-insensitive).

    Raises:
        ValueError: If ``day_testid`` isn't a recognized weekday.
    """
    key = day_testid.strip().lower()
    if key not in _DAY_OFFSETS:
        raise ValueError(f"unknown day column: {day_testid!r}")
    return week_start + timedelta(days=_DAY_OFFSETS[key])
