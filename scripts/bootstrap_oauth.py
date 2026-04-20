"""One-time OAuth flow to generate .secrets/token.json.

Run this from your laptop (NOT in a container). It pops a browser tab,
asks you to consent to the calendar.events scope, then writes the token
to the path in your .env (default: .secrets/token.json).

After this, the daily sync uses the refresh_token in token.json and never
needs interactive consent again -- as long as we run at least once every
6 months to keep the refresh token alive.

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
    print(f"\nCredentials path: {cfg.gcal_credentials_path}")
    print(f"Token path:       {cfg.gcal_token_path}")
    print("Configured employees / calendars:")
    for emp in cfg.employees:
        print(f"  - {emp.name} -> {emp.calendar_id}")
    print()

    creds = load_credentials(
        cfg.gcal_credentials_path,
        cfg.gcal_token_path,
        credentials_data=cfg.gcal_credentials_data,
        token_data=cfg.gcal_token_data,
    )
    service = build_service(creds)

    # Verify by calling events().list -- this works under calendar.events scope.
    # calendars().get() needs broader scope (calendar.readonly) which we don't request.
    now = datetime.now(UTC)
    horizon = now + timedelta(days=14)
    print("OAuth OK. Verifying event access on each calendar...\n")
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
        except Exception as exc:
            print(f"  [FAIL] {emp.name}: {type(exc).__name__}: {exc}")

    print(f"\nToken written to: {cfg.gcal_token_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
