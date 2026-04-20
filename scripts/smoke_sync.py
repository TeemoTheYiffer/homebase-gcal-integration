"""End-to-end smoke test: scrape Homebase + sync to GCal.

Run this AFTER bootstrap_oauth.py has produced .secrets/token.json.

Usage:
    .\\.venv\\Scripts\\python.exe scripts\\smoke_sync.py
    .\\.venv\\Scripts\\python.exe scripts\\smoke_sync.py --headed   # watch the browser
    .\\.venv\\Scripts\\python.exe scripts\\smoke_sync.py --dry-run  # scrape only, no GCal writes
"""

from __future__ import annotations

import argparse
import logging
import sys
from datetime import date
from zoneinfo import ZoneInfo

from homebase_sync.calendar_sync import sync_all
from homebase_sync.config import load_config
from homebase_sync.parser import parse_week_html
from homebase_sync.scraper import fetch_weeks, weeks_to_scrape


def main() -> int:
    args = _parse_args()
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
    )

    cfg = load_config()
    tz = ZoneInfo(cfg.timezone)
    weeks = weeks_to_scrape(date.today())

    print(f"\nWeeks to sync: {[w.isoformat() for w in weeks]}")
    print(f"Employees:     {list(cfg.employee_names)}")
    print(f"Headless:      {not args.headed}")
    print(f"Dry run:       {args.dry_run}\n")

    htmls = fetch_weeks(
        cfg.homebase_email,
        cfg.homebase_password,
        weeks,
        headless=not args.headed,
    )

    scraped: dict = {}
    for week, html in htmls.items():
        scraped[week] = parse_week_html(html, week, cfg.employee_names, tz)
        print(f"Week of {week.isoformat()}:")
        for name, shifts in scraped[week].items():
            print(f"  {name}: {len(shifts)} shift(s)")
        print()

    if args.dry_run:
        print("Dry run -- skipping GCal writes.")
        return 0

    print("Syncing to Google Calendar...\n")
    reports = sync_all(cfg, scraped)
    for r in reports:
        print(
            f"  {r.employee_name} -> {r.calendar_id}: "
            f"+{r.created} ~{r.updated} -{r.deleted}"
        )
    print()
    return 0


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--headed", action="store_true", help="Show the browser during scrape")
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="Scrape and parse only; skip Google Calendar writes",
    )
    return p.parse_args()


if __name__ == "__main__":
    sys.exit(main())
