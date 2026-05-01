"""One-time cleanup: delete all homebase*-prefixed events from configured calendars.

Use case: when migrating from OAuth user auth to a service account, the old
events were created by your user identity and the SA can't UPDATE them
(Calendar API: ``forbiddenForNonCreator``). Delete them with your user creds
so the next SA sync run can INSERT fresh events as their creator.

Run this LOCALLY with your user ADC (the account that created the original
events). Looks at the next 4 weeks; safe to re-run.

Usage:
    .\\.venv\\Scripts\\python.exe scripts\\cleanup_legacy_events.py
    .\\.venv\\Scripts\\python.exe scripts\\cleanup_legacy_events.py --dry-run
"""

from __future__ import annotations

import argparse
import logging
import sys
from datetime import UTC, datetime, timedelta

from homebase_sync.calendar_sync import EVENT_ID_PREFIX, build_service, load_credentials
from homebase_sync.config import load_config


def main() -> int:
    args = _parse_args()
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
    )
    cfg = load_config()
    creds = load_credentials()
    service = build_service(creds)

    now = datetime.now(UTC)
    window_start = now - timedelta(days=args.days_back)
    horizon = now + timedelta(days=args.days_forward)
    print(f"\nWindow: {window_start.date()} -> {horizon.date()}")
    print(f"Dry run: {args.dry_run}\n")

    total_deleted = 0
    for emp in cfg.employees:
        print(f"{emp.name} ({emp.calendar_id}):")
        page_token = None
        deleted = 0
        while True:
            resp = (
                service.events()
                .list(
                    calendarId=emp.calendar_id,
                    timeMin=window_start.isoformat(),
                    timeMax=horizon.isoformat(),
                    pageToken=page_token,
                    maxResults=2500,
                    singleEvents=True,
                )
                .execute()
            )
            for event in resp.get("items", []):
                event_id = event.get("id", "")
                if not event_id.startswith(EVENT_ID_PREFIX):
                    continue
                summary = event.get("summary", "(no title)")
                if args.dry_run:
                    print(f"  [DRY] would delete {event_id}: {summary}")
                else:
                    service.events().delete(calendarId=emp.calendar_id, eventId=event_id).execute()
                    print(f"  deleted {event_id}: {summary}")
                deleted += 1
            page_token = resp.get("nextPageToken")
            if not page_token:
                break
        print(f"  -> {deleted} event(s) {'would be deleted' if args.dry_run else 'deleted'}\n")
        total_deleted += deleted

    print(f"Total: {total_deleted} event(s) {'(dry run)' if args.dry_run else 'deleted'}")
    if not args.dry_run and total_deleted:
        print("\nNext: re-run the Cloud Run Job. The SA will INSERT fresh events as creator.")
        print("  gcloud run jobs execute homebase-sync --region=us-west1 --wait")
    return 0


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--dry-run", action="store_true", help="List events without deleting")
    p.add_argument(
        "--days-back",
        type=int,
        default=60,
        help="How many days into the past to scan (default: 60)",
    )
    p.add_argument(
        "--days-forward",
        type=int,
        default=28,
        help="How many days into the future to scan (default: 28)",
    )
    return p.parse_args()


if __name__ == "__main__":
    sys.exit(main())
