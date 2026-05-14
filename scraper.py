#!/usr/bin/env python3
"""
DealerRater scraper — requests-based, no Playwright.
Uses the public S3 sitemap to get all dealer URLs, then scrapes detail pages.
"""

import logging
import random
import re
import time
from typing import Optional

import requests
from bs4 import BeautifulSoup

import config

log = logging.getLogger("scraper")

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
}

SITEMAP_URL = (
    "https://uploads-dealerrater.s3.amazonaws.com/sitemap/US/dealership-reviews-sitemap.xml"
)

# OEM brand keywords to match against dealer URL slugs
OEM_KEYWORDS: dict[str, list[str]] = {
    "Ford":         ["ford"],
    "Toyota":       ["toyota"],
    "Chevrolet":    ["chevrolet", "chevy"],
    "Chrysler":     ["chrysler"],
    "Mercedes-Benz": ["mercedes"],
}


def build_session() -> requests.Session:
    s = requests.Session()
    s.headers.update(HEADERS)
    return s


def fetch_sitemap_urls(session: requests.Session) -> list[str]:
    """Download the dealership-reviews sitemap and return all dealer URLs."""
    log.info("Downloading sitemap from S3 ...")
    r = _safe_get(session, SITEMAP_URL)
    if not r:
        return []
    urls = re.findall(
        r"<loc>(https://www\.dealerrater\.com/dealer/[^<]+)</loc>", r
    )
    log.info("Sitemap: %d total dealer URLs", len(urls))
    return urls


def filter_urls_by_brand(urls: list[str], oem: str) -> list[str]:
    """Return URLs whose slug contains a keyword matching the OEM brand."""
    keywords = OEM_KEYWORDS.get(oem, [oem.lower()])
    matched = [u for u in urls if any(kw in u.lower() for kw in keywords)]
    log.info("%s: %d URLs matched in sitemap", oem, len(matched))
    return matched


def scrape_dealer_page(session: requests.Session, url: str) -> Optional[dict]:
    """
    Scrape a single dealer detail page.
    Returns a dict with all fields or None on failure.
    """
    html = _safe_get(session, url)
    if not html:
        return None

    soup = BeautifulSoup(html, "lxml")

    # Try schema.org JSON-LD first — most reliable
    data = _parse_json_ld(soup)

    # Fallback to HTML selectors
    dealer_name = (
        data.get("name")
        or _text(soup, "h1.dealer-name, h1.dealership-name, h1")
    )
    if not dealer_name or "error" in dealer_name.lower():
        return None

    address = data.get("address", {})
    city  = address.get("addressLocality") or _text(soup, ".city, [class*='city']")
    state = address.get("addressRegion")   or _text(soup, ".state, [class*='state']")

    # Parse city/state from combined address text if needed
    if not city or not state:
        addr_text = _text(soup, ".dealer-address, [class*='address'], address")
        if addr_text and "," in addr_text:
            parts = addr_text.split(",")
            if not city:
                city = parts[-2].strip() if len(parts) >= 2 else ""
            if not state:
                state_zip = parts[-1].strip().split()
                state = state_zip[0] if state_zip else ""

    # Rating
    rating = (
        data.get("aggregateRating", {}).get("ratingValue")
        or _text(soup, "[class*='rating-static'], [class*='star-rating'], [itemprop='ratingValue']")
    )

    # Review count
    review_count_raw = (
        str(data.get("aggregateRating", {}).get("reviewCount", ""))
        or _text(soup, "[class*='review-count'], [itemprop='reviewCount']")
    )
    review_count = _parse_int(review_count_raw)

    # Phone
    phone_el = soup.select_one("a[href^='tel:'], [class*='phone']")
    phone = ""
    if phone_el:
        href = phone_el.get("href", "")
        phone = href.replace("tel:", "").strip() if href.startswith("tel:") else phone_el.get_text(strip=True)

    # Website
    website = data.get("url") or ""
    if not website:
        for a in soup.find_all("a", href=True):
            href = a["href"]
            if href.startswith("http") and "dealerrater" not in href and "dealerrater" not in a.get_text().lower():
                website = href
                break

    # ICP staff
    icp_names, icp_titles = _parse_icp_staff(soup)

    return {
        "dealer_name":      dealer_name.strip(),
        "city":             city.strip() if city else "",
        "state":            state.strip() if state else "",
        "rating":           str(rating).strip() if rating else "",
        "review_count":     review_count,
        "website":          website.rstrip("/"),
        "phone":            phone,
        "icp_staff_names":  " | ".join(icp_names),
        "icp_staff_titles": " | ".join(icp_titles),
        "dealer_url":       url,
    }


def _parse_json_ld(soup: BeautifulSoup) -> dict:
    """Extract schema.org structured data from JSON-LD script tags."""
    import json
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(script.string or "")
            if isinstance(data, list):
                data = data[0]
            if data.get("@type") in ("AutoDealer", "LocalBusiness", "Organization"):
                return data
        except Exception:
            pass
    return {}


def _parse_icp_staff(soup: BeautifulSoup) -> tuple[list[str], list[str]]:
    names, titles = [], []
    # Try multiple selectors for staff sections
    members = (
        soup.select("[class*='employee-review']") or
        soup.select("[class*='staff-member']") or
        soup.select("[class*='employee-item']")
    )
    for member in members:
        name_el  = member.select_one("[class*='employee-name'], [class*='staff-name']")
        title_el = member.select_one("[class*='employee-title'], [class*='staff-title']")
        name  = name_el.get_text(strip=True)  if name_el  else ""
        title = title_el.get_text(strip=True) if title_el else ""
        if name and _is_icp_title(title):
            names.append(name)
            titles.append(title)
    return names, titles


def _is_icp_title(title: str) -> bool:
    t = title.lower()
    return any(kw in t for kw in config.ICP_TITLE_KEYWORDS)


def _text(soup: BeautifulSoup, selector: str) -> str:
    el = soup.select_one(selector)
    return el.get_text(strip=True) if el else ""


def _parse_int(text: str) -> int:
    m = re.search(r"[\d,]+", str(text))
    return int(m.group(0).replace(",", "")) if m else 0


def _safe_get(session: requests.Session, url: str) -> Optional[str]:
    for attempt in range(config.MAX_RETRIES):
        try:
            r = session.get(url, timeout=25)
            r.raise_for_status()
            time.sleep(config.RATE_LIMIT_DETAIL + random.uniform(0, 0.5))
            return r.text
        except Exception as exc:
            wait = 2 ** attempt
            log.warning("Attempt %d/%d failed for %s: %s. Retry in %ds",
                        attempt + 1, config.MAX_RETRIES, url, exc, wait)
            time.sleep(wait)
    log.error("All retries exhausted: %s", url)
    return None
