"""Verify ADC can write events on every calendar in employees.toml.

Replaces the older OAuth bootstrap flow now that we use Application Default
Credentials throughout.

Locally: run after `gcloud auth application-default login` to confirm your
user account has edit rights on each calendar.

In Cloud Run: not needed (the runtime SA exercises this on every execution).

Usage:
    .\\.venv\\Scripts\\python.exe scripts\\bootstrap_oauth.py
"""

from __future__ import annotations

import logging
import sys
from datetime import UTC, datetime, timedelta

from homebase_sync.calendar_sync import build_service, load_credentials
from homebase_sync.config import load_config


def main() -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
    )
    cfg = load_config()
    print("Configured employees / calendars:")
    for emp in cfg.employees:
        print(f"  - {emp.name} -> {emp.calendar_id}")
    print()

    creds = load_credentials()
    service = build_service(creds)

    now = datetime.now(UTC)
    horizon = now + timedelta(days=14)
    print("Verifying event access on each calendar...\n")
    failures = 0
    for emp in cfg.employees:
        try:
            resp = (
                service.events()
                .list(
                    calendarId=emp.calendar_id,
                    timeMin=now.isoformat(),
                    timeMax=horizon.isoformat(),
                    maxResults=1,
                    singleEvents=True,
                )
                .execute()
            )
            count = len(resp.get("items", []))
            print(f"  [OK] {emp.name}: events().list returned {count} event(s) in next 14 days")
        except Exception as exc:  # diagnostic only
            failures += 1
            print(f"  [FAIL] {emp.name}: {type(exc).__name__}: {exc}")

    if failures:
        print(
            f"\n{failures} calendar(s) inaccessible. Share the calendar with the "
            "principal you're authenticated as ('Make changes to events')."
        )
        return 1
    print("\nAll calendars accessible.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
