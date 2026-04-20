"""Production entrypoint: ``python -m homebase_sync``.

Loads config, scrapes the current + next week, parses each, and syncs to
each employee's calendar. Exits 0 on success, 1 on any unhandled failure
(so cron / Cloud Run Job retry logic can react).
"""

from __future__ import annotations

import logging
import sys
from datetime import date
from zoneinfo import ZoneInfo

from .calendar_sync import sync_all
from .config import load_config
from .parser import parse_week_html
from .scraper import fetch_weeks, weeks_to_scrape


def main() -> int:
    cfg = load_config()
    logging.basicConfig(
        level=getattr(logging, cfg.log_level.upper(), logging.INFO),
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
    )
    logger = logging.getLogger("homebase_sync")

    try:
        tz = ZoneInfo(cfg.timezone)
        weeks = weeks_to_scrape(date.today())
        logger.info(
            "starting sync: %d week(s), %d employee(s) configured",
            len(weeks),
            len(cfg.employees),
        )

        htmls = fetch_weeks(
            cfg.homebase_email,
            cfg.homebase_password,
            weeks,
            headless=True,
        )
        scraped = {
            week: parse_week_html(html, week, cfg.employee_names, tz)
            for week, html in htmls.items()
        }

        reports = sync_all(cfg, scraped)
        for r in reports:
            logger.info(
                "%s -> %s: +%d ~%d -%d",
                r.employee_name,
                r.calendar_id,
                r.created,
                r.updated,
                r.deleted,
            )
        logger.info("sync complete")
        return 0
    except Exception:
        logger.exception("sync failed")
        return 1


if __name__ == "__main__":
    sys.exit(main())
