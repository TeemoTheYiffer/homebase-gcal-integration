"""Domain model for a single Homebase shift."""

from dataclasses import dataclass
from datetime import date, datetime


@dataclass(frozen=True, slots=True)
class Shift:
    """A scheduled work shift parsed from the Homebase weekly grid.

    Attributes:
        shift_id: Numeric Homebase shift identifier (from ``data-testid``).
        shift_date: Calendar date the shift falls on.
        start: Timezone-aware start datetime.
        end: Timezone-aware end datetime. May be on the day after ``shift_date``
            for shifts that wrap past midnight (e.g. closing shifts).
        role: Role label as shown on the shift tile (e.g. ``"Prep/Fryer"``).
    """

    shift_id: str
    shift_date: date
    start: datetime
    end: datetime
    role: str

    @property
    def gcal_event_id(self) -> str:
        """Stable Google Calendar event ID derived from shift ID + date.

        GCal event IDs must match ``[a-v0-9]{5,1024}``. Lowercase ``homebase`` +
        numeric shift ID + ``d`` separator + ``YYYYMMDD`` always satisfies that.

        Including the date in the ID has two benefits:
          1. Rescheduled shifts get a fresh ID (delete-diff handles the swap).
          2. Avoids ID collision with previously-cancelled events whose IDs
             stay reserved by Google for hours after deletion.
        """
        return f"homebase{self.shift_id}d{self.shift_date.strftime('%Y%m%d')}"
