#!/usr/bin/env python3
"""
Playwright async wrapper for DealerRater.
Owns the browser lifecycle: one Chromium process, one context, many cheap pages.
"""

import asyncio
import logging
import random
from typing import Optional

from playwright.async_api import (
    async_playwright,
    Browser,
    BrowserContext,
    Playwright,
    Error as PlaywrightError,
)

import config
from parser import SELECTORS

log = logging.getLogger("scraper")

_WEBDRIVER_PATCH = (
    "Object.defineProperty(navigator, 'webdriver', {get: () => undefined});"
)

_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)


class DealerRaterScraper:
    """
    Async context manager.  Use as:

        async with DealerRaterScraper() as scraper:
            html = await scraper.fetch_listing_page(url)
    """

    def __init__(self) -> None:
        self._playwright: Optional[Playwright]      = None
        self._browser:    Optional[Browser]         = None
        self._context:    Optional[BrowserContext]  = None

    async def __aenter__(self) -> "DealerRaterScraper":
        self._playwright = await async_playwright().start()
        self._browser = await self._playwright.chromium.launch(
            headless=False,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--disable-gpu",
                "--window-size=1280,800",
            ],
        )
        self._context = await self._browser.new_context(
            user_agent=_USER_AGENT,
            viewport={"width": 1280, "height": 800},
            locale="en-US",
            timezone_id="America/New_York",
            extra_http_headers={
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.9",
                "Accept-Encoding": "gzip, deflate, br",
                "Upgrade-Insecure-Requests": "1",
            },
        )
        return self

    async def __aexit__(self, *_) -> None:
        if self._context:
            await self._context.close()
        if self._browser:
            await self._browser.close()
        if self._playwright:
            await self._playwright.stop()

    # ── Public fetch methods ───────────────────────────────────────────────────

    async def fetch_listing_page(self, url: str) -> Optional[str]:
        return await self._fetch_page(
            url,
            wait_selector=SELECTORS["dealer_cards"],
            rate_limit=config.RATE_LIMIT_LISTING,
        )

    async def fetch_detail_page(self, url: str) -> Optional[str]:
        return await self._fetch_page(
            url,
            wait_selector=SELECTORS["detail_phone"],
            rate_limit=config.RATE_LIMIT_DETAIL,
        )

    async def fetch_raw(self, url: str) -> Optional[str]:
        """Fetch without waiting for a specific selector — used by --probe."""
        return await self._fetch_page(url, wait_selector=None, rate_limit=1.0)

    # ── Core fetch ─────────────────────────────────────────────────────────────

    async def _fetch_page(
        self,
        url: str,
        wait_selector: Optional[str],
        rate_limit: float,
    ) -> Optional[str]:
        for attempt in range(config.MAX_RETRIES):
            try:
                page = await self._context.new_page()
                await page.add_init_script(_WEBDRIVER_PATCH)
                await page.goto(url, wait_until="domcontentloaded", timeout=30_000)
                if wait_selector:
                    try:
                        await page.wait_for_selector(wait_selector, timeout=15_000)
                    except PlaywrightError:
                        # Selector not found — page may still have useful HTML
                        log.debug("Selector '%s' not found on %s", wait_selector, url)
                html = await page.content()
                await page.close()
                await asyncio.sleep(rate_limit + random.uniform(0.0, 0.5))
                return html
            except PlaywrightError as exc:
                wait = 2 ** attempt
                log.warning("Attempt %d/%d failed for %s: %s. Retry in %ds",
                            attempt + 1, config.MAX_RETRIES, url, exc, wait)
                try:
                    await page.close()
                except Exception:
                    pass
                if attempt < config.MAX_RETRIES - 1:
                    await asyncio.sleep(wait)

        log.error("All retries exhausted for %s", url)
        return None
