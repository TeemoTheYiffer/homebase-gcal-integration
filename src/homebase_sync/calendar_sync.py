"""Google Calendar upsert/delete for Homebase shifts.

The strategy is idempotent:
  * Each Shift maps to a deterministic GCal event ID (``homebase<shift_id>``).
  * For each scraped shift we ``get`` -- if 404, ``insert``; else ``update``.
  * After upserts, list events in the sync window with our prefix and delete
    any whose IDs aren't in the just-scraped set. That handles shift removals.

Auth uses Application Default Credentials. In Cloud Run that's the runtime
service account (``homebase-sync-runner@...``) injected via the metadata
server. Locally that's whatever ``gcloud auth application-default login``
set up. Each target calendar must be shared with the principal (SA email or
your user email) with at least "Make changes to events" rights.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

import google.auth
from google.auth.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from .config import AppConfig
from .models import Shift

logger = logging.getLogger("homebase_sync.calendar_sync")

SCOPES = ["https://www.googleapis.com/auth/calendar.events"]
EVENT_ID_PREFIX = "homebase"
WEEK_URL_TEMPLATE = "https://app.joinhomebase.com/schedule/employee/week/{date}"


@dataclass(frozen=True, slots=True)
class SyncReport:
    employee_name: str
    calendar_id: str
    created: int
    updated: int
    deleted: int

    @property
    def total_changes(self) -> int:
        return self.created + self.updated + self.deleted


def load_credentials() -> Credentials:
    """Get credentials from Application Default Credentials.

    In Cloud Run: returns the runtime SA's credentials from the metadata
    server (no key file, no expiry concerns).

    Locally: returns whatever ``gcloud auth application-default login`` set
    up. The user account must have edit rights on each target calendar.

    Either way, the *principal* (SA email or user email) must be granted
    "Make changes to events" on every calendar in employees.toml.
    """
    creds, _ = google.auth.default(scopes=SCOPES)
    return creds


def build_service(credentials: Credentials):
    """Construct the Calendar API client."""
    return build("calendar", "v3", credentials=credentials, cache_discovery=False)


def build_event_body(shift: Shift, employee_name: str, timezone: str) -> dict:
    """Construct the GCal event body for a Homebase shift.

    The ``id`` field makes inserts idempotent: re-inserting the same ID
    returns 409, which we sidestep by using ``get`` -> ``update``/``insert``.
    """
    week_url = WEEK_URL_TEMPLATE.format(date=_monday_of(shift.shift_date).isoformat())
    return {
        "id": shift.gcal_event_id,
        "summary": f"{employee_name.split()[0]} Work: {shift.role}",
        "description": (
            f"Homebase shift ID: {shift.shift_id}\n"
            f"Employee: {employee_name}\n"
            "Synced by homebase-sync"
        ),
        "start": {"dateTime": shift.start.isoformat(), "timeZone": timezone},
        "end": {"dateTime": shift.end.isoformat(), "timeZone": timezone},
        "source": {"title": "Homebase Schedule", "url": week_url},
    }


def sync_window(week_starts: Iterable[date], tz: ZoneInfo) -> tuple[datetime, datetime]:
    """Return (window_start, window_end) spanning the listed weeks (end exclusive)."""
    starts = sorted(set(week_starts))
    if not starts:
        raise ValueError("at least one week_start required")
    window_start = datetime.combine(starts[0], time.min, tzinfo=tz)
    window_end = datetime.combine(starts[-1] + timedelta(days=7), time.min, tzinfo=tz)
    return window_start, window_end


def sync_all(
    cfg: AppConfig,
    scraped: dict[date, dict[str, list[Shift]]],
) -> list[SyncReport]:
    """Sync the scraped weeks to each employee's calendar.

    Args:
        cfg: Loaded app config (provides credentials, calendar map, timezone).
        scraped: ``{week_start: {employee_name: [shifts]}}`` -- exactly the shape
            produced by mapping ``parser.parse_week_html`` over each scraped week.

    Returns:
        One SyncReport per employee that has a calendar configured.
    """
    creds = load_credentials()
    service = build_service(creds)
    tz = ZoneInfo(cfg.timezone)
    window_start, window_end = sync_window(scraped.keys(), tz)

    by_employee: dict[str, list[Shift]] = defaultdict(list)
    for week_data in scraped.values():
        for name, shifts in week_data.items():
            by_employee[name].extend(shifts)

    reports: list[SyncReport] = []
    for name, shifts in by_employee.items():
        try:
            calendar_id = cfg.calendar_for(name)
        except KeyError:
            logger.warning("no calendar configured for %r; skipping %d shift(s)", name, len(shifts))
            continue
        reports.append(
            _sync_employee(
                service=service,
                calendar_id=calendar_id,
                employee_name=name,
                shifts=shifts,
                timezone=cfg.timezone,
                window_start=window_start,
                window_end=window_end,
            )
        )
    return reports


def _sync_employee(
    *,
    service,
    calendar_id: str,
    employee_name: str,
    shifts: list[Shift],
    timezone: str,
    window_start: datetime,
    window_end: datetime,
) -> SyncReport:
    """Upsert all shifts and delete stale events for one employee/calendar."""
    logger.info(
        "syncing %d shift(s) for %s -> %s",
        len(shifts),
        employee_name,
        calendar_id,
    )
    created = updated = 0
    keep_ids: set[str] = set()
    for shift in shifts:
        action = _upsert_shift(service, calendar_id, shift, employee_name, timezone)
        keep_ids.add(shift.gcal_event_id)
        if action == "created":
            created += 1
        else:
            updated += 1

    deleted = _delete_stale_events(
        service=service,
        calendar_id=calendar_id,
        keep_event_ids=keep_ids,
        window_start=window_start,
        window_end=window_end,
    )
    report = SyncReport(
        employee_name=employee_name,
        calendar_id=calendar_id,
        created=created,
        updated=updated,
        deleted=deleted,
    )
    logger.info("sync done for %s: +%d ~%d -%d", employee_name, created, updated, deleted)
    return report


def _upsert_shift(
    service,
    calendar_id: str,
    shift: Shift,
    employee_name: str,
    timezone: str,
) -> str:
    """Returns ``"created"``, ``"updated"``, or ``"recreated"``."""
    body = build_event_body(shift, employee_name, timezone)
    try:
        service.events().get(calendarId=calendar_id, eventId=shift.gcal_event_id).execute()
    except HttpError as exc:
        if exc.resp.status == 404:
            service.events().insert(calendarId=calendar_id, body=body).execute()
            return "created"
        raise

    try:
        service.events().update(
            calendarId=calendar_id, eventId=shift.gcal_event_id, body=body
        ).execute()
        return "updated"
    except HttpError as exc:
        # Calendar API forbids updating events whose creator is a different
        # principal (legacy events from before the SA migration). Delete and
        # re-insert so the SA becomes the new creator. "Make changes to
        # events" perm allows delete regardless of creator.
        if exc.resp.status == 403 and "forbiddenForNonCreator" in str(exc):
            logger.info("event %s has different creator; recreating", shift.gcal_event_id)
            service.events().delete(calendarId=calendar_id, eventId=shift.gcal_event_id).execute()
            service.events().insert(calendarId=calendar_id, body=body).execute()
            return "recreated"
        raise


def _delete_stale_events(
    *,
    service,
    calendar_id: str,
    keep_event_ids: set[str],
    window_start: datetime,
    window_end: datetime,
) -> int:
    """Delete homebase-prefixed events in the window that aren't in keep_event_ids."""
    deleted = 0
    page_token: str | None = None
    while True:
        resp = (
            service.events()
            .list(
                calendarId=calendar_id,
                timeMin=window_start.isoformat(),
                timeMax=window_end.isoformat(),
                pageToken=page_token,
                maxResults=2500,
                singleEvents=True,
            )
            .execute()
        )
        for event in resp.get("items", []):
            event_id = event.get("id", "")
            if event_id.startswith(EVENT_ID_PREFIX) and event_id not in keep_event_ids:
                logger.info("deleting stale event %s from %s", event_id, calendar_id)
                service.events().delete(calendarId=calendar_id, eventId=event_id).execute()
                deleted += 1
        page_token = resp.get("nextPageToken")
        if not page_token:
            break
    return deleted


def _monday_of(d: date) -> date:
    return d - timedelta(days=d.weekday())
