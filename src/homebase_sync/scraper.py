"""Headless Playwright login + weekly schedule fetch.

Single login per run; one browser context shared across all week fetches.
We deliberately don't persist cookies -- a fresh login each run is more
self-healing than chasing silent session expiry.
"""

from __future__ import annotations

import logging
from collections.abc import Iterable
from datetime import date, timedelta

from playwright.sync_api import Page, TimeoutError as PlaywrightTimeoutError, sync_playwright
from playwright_stealth import Stealth

logger = logging.getLogger("homebase_sync.scraper")

LOGIN_URL = "https://app.joinhomebase.com/accounts/sign-in"
WEEK_URL_TEMPLATE = "https://app.joinhomebase.com/schedule/employee/week/{date}"
SHIFT_GRID_SELECTOR = ".EWVEmployeeRow"

# Login form selectors -- prefer Homebase's stable data-testids over generic CSS.
# The email field is actually type="text" (not "email"), so the data-testid is required.
EMAIL_INPUT_SELECTOR = '[data-testid="EmailSignInForm__email-input"]'
PASSWORD_INPUT_SELECTOR = '[data-testid="EmailSignInForm__password-input"]'
SUBMIT_BUTTON_SELECTOR = 'button[type="submit"]'


class LoginError(Exception):
    """Raised when the Homebase login flow doesn't reach a signed-in state."""


class ScrapeError(Exception):
    """Raised when a week page never renders the expected schedule grid."""


def monday_of_week(d: date) -> date:
    """Return the Monday on or before ``d`` (``weekday()`` is 0 for Monday)."""
    return d - timedelta(days=d.weekday())


def weeks_to_scrape(today: date, count: int = 2) -> list[date]:
    """Return Mondays for the current week and the next ``count - 1`` weeks."""
    if count < 1:
        raise ValueError(f"count must be >= 1, got {count}")
    start = monday_of_week(today)
    return [start + timedelta(weeks=i) for i in range(count)]


def fetch_weeks(
    email: str,
    password: str,
    week_starts: Iterable[date],
    *,
    headless: bool = True,
    timeout_ms: int = 30_000,
) -> dict[date, str]:
    """Login once and return ``{week_start: rendered_html}`` for each week.

    Args:
        email: Homebase account email.
        password: Homebase account password.
        week_starts: Mondays to fetch. Order is preserved in the result dict.
        headless: Set False for local debugging to watch the browser.
        timeout_ms: Per-action timeout. Login and each navigation get this budget.

    Raises:
        LoginError: If login doesn't redirect away from ``/sign-in`` in time.
        ScrapeError: If a schedule page never renders the grid in time.
    """
    weeks = list(week_starts)
    out: dict[date, str] = {}
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless)
        try:
            context = browser.new_context()
            # Patches navigator.webdriver, plugin list, WebGL fingerprint, etc.
            # Homebase rejects vanilla Playwright Chromium with a generic
            # "incorrect credentials" message; stealth gets us past that.
            Stealth().apply_stealth_sync(context)
            page = context.new_page()
            page.set_default_timeout(timeout_ms)
            _login(page, email, password)
            for week in weeks:
                out[week] = _fetch_week_html(page, week)
        finally:
            browser.close()
    return out


def _login(page: Page, email: str, password: str) -> None:
    logger.info("logging in to Homebase as %s", email)
    page.goto(LOGIN_URL)
    # Type per-keystroke (with delay) instead of fill() -- some validators
    # check for real keyboard events, not just .value mutations.
    page.locator(EMAIL_INPUT_SELECTOR).press_sequentially(email, delay=50)
    page.locator(PASSWORD_INPUT_SELECTOR).press_sequentially(password, delay=50)
    page.click(SUBMIT_BUTTON_SELECTOR)
    try:
        page.wait_for_url(lambda url: "sign-in" not in url)
    except PlaywrightTimeoutError as exc:
        raise LoginError(
            "did not redirect away from /sign-in -- check credentials, MFA, or CAPTCHA"
        ) from exc
    logger.info("login succeeded; landed on %s", page.url)


def _fetch_week_html(page: Page, week_start: date) -> str:
    url = WEEK_URL_TEMPLATE.format(date=week_start.isoformat())
    logger.info("fetching week %s -> %s", week_start.isoformat(), url)
    page.goto(url)
    try:
        page.wait_for_selector(SHIFT_GRID_SELECTOR)
    except PlaywrightTimeoutError as exc:
        raise ScrapeError(f"schedule grid never rendered for week {week_start}") from exc
    return page.content()
