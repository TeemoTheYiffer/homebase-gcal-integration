"""Smoke test for the Playwright scraper.

Loads creds from .env, fetches current + next week, prints summary, runs the
parser against each week, and optionally dumps raw HTML to scripts/_dumps/
for inspection.

Usage:
    .\\.venv\\Scripts\\python.exe scripts\\smoke_scrape.py            # headless
    .\\.venv\\Scripts\\python.exe scripts\\smoke_scrape.py --headed   # watch the browser
    .\\.venv\\Scripts\\python.exe scripts\\smoke_scrape.py --dump     # save html to disk
"""

from __future__ import annotations

import argparse
import logging
import sys
from datetime import date
from pathlib import Path
from zoneinfo import ZoneInfo

from homebase_sync.config import load_config
from homebase_sync.parser import parse_week_html
from homebase_sync.scraper import fetch_weeks, weeks_to_scrape

DUMP_DIR = Path(__file__).parent / "_dumps"


def main() -> int:
    args = _parse_args()
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
    )

    cfg = load_config()
    tz = ZoneInfo(cfg.timezone)
    weeks = weeks_to_scrape(date.today())
    print(f"\nScraping weeks: {[w.isoformat() for w in weeks]}")
    print(f"Employees in config: {list(cfg.employee_names)}")
    print(f"Headless: {not args.headed}\n")

    htmls = fetch_weeks(
        cfg.homebase_email,
        cfg.homebase_password,
        weeks,
        headless=not args.headed,
    )

    if args.dump:
        DUMP_DIR.mkdir(exist_ok=True)
        for week, html in htmls.items():
            path = DUMP_DIR / f"week_{week.isoformat()}.html"
            path.write_text(html, encoding="utf-8")
            print(f"  dumped {path} ({len(html):,} bytes)")
        print()

    for week, html in htmls.items():
        shifts_by_employee = parse_week_html(html, week, cfg.employee_names, tz)
        print(f"Week of {week.isoformat()}:")
        for name, shifts in shifts_by_employee.items():
            print(f"  {name}: {len(shifts)} shift(s)")
            for s in shifts:
                print(
                    f"    - {s.shift_date} {s.start.strftime('%H:%M')}-"
                    f"{s.end.strftime('%H:%M')} {s.role} (id={s.shift_id})"
                )
        print()
    return 0


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--headed", action="store_true", help="Show the browser window")
    p.add_argument("--dump", action="store_true", help="Save raw HTML to scripts/_dumps/")
    return p.parse_args()


if __name__ == "__main__":
    sys.exit(main())
