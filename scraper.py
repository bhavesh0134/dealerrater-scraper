#!/usr/bin/env python3
"""
DealerRater scraper — requests-based, no Playwright.

Two modes:
  sitemap  — download S3 sitemap, filter by brand keyword in URL slug (original)
  listing  — hit brand+state listing pages to catch ALL dealers for that brand,
             including multi-brand dealers whose URL slug has no brand keyword
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

# OEM brand keywords to match against dealer URL slugs (sitemap mode)
OEM_KEYWORDS: dict[str, list[str]] = {
    "Ford":          ["ford"],
    "Toyota":        ["toyota"],
    "Chevrolet":     ["chevrolet", "chevy"],
    "Chrysler":      ["chrysler"],
    "Mercedes-Benz": ["mercedes"],
    "Jeep":          ["jeep"],
    "Honda":         ["honda"],
    "Nissan":        ["nissan"],
    "KIA":           ["kia"],
    "GMC":           ["gmc"],
    "Dodge":         ["dodge"],
    "Ram":           ["ram"],
    "Cadillac":      ["cadillac"],
    "Subaru":        ["subaru"],
    "Volkswagen":    ["volkswagen", "vw"],
    "Mazda":         ["mazda"],
    "BMW":           ["bmw"],
    "Mitsubishi":    ["mitsubishi"],
    "Audi":          ["audi"],
    "Lexus":         ["lexus"],
    "Acura":         ["acura"],
    "Volvo":         ["volvo"],
    "Infiniti":      ["infiniti"],
    "Buick":         ["buick"],
    "Mini":          ["mini"],
    "Land-Rover":    ["land-rover"],
    "Porsche":       ["porsche"],
    "Jaguar":        ["jaguar"],
}

# Renowned brands for full-sitemap mode — all OEM_KEYWORDS minus DNC (Hyundai, Genesis)
RENOWNED_BRANDS: list[str] = [b for b in OEM_KEYWORDS]

# Brand name keywords for detecting brand from dealer name (broader than URL slug keywords)
BRAND_NAME_KEYWORDS: dict[str, list[str]] = {
    "Ford":          ["ford"],
    "Toyota":        ["toyota"],
    "Chevrolet":     ["chevrolet", "chevy"],
    "Chrysler":      ["chrysler"],
    "Mercedes-Benz": ["mercedes", "mercedes-benz"],
    "Jeep":          ["jeep"],
    "Honda":         ["honda"],
    "Nissan":        ["nissan"],
    "KIA":           ["kia"],
    "GMC":           ["gmc"],
    "Dodge":         ["dodge"],
    "Ram":           ["ram"],
    "Cadillac":      ["cadillac"],
    "Subaru":        ["subaru"],
    "Volkswagen":    ["volkswagen", " vw "],
    "Mazda":         ["mazda"],
    "BMW":           ["bmw"],
    "Mitsubishi":    ["mitsubishi"],
    "Audi":          ["audi"],
    "Lexus":         ["lexus"],
    "Acura":         ["acura"],
    "Volvo":         ["volvo"],
    "Infiniti":      ["infiniti"],
    "Buick":         ["buick"],
    "Mini":          ["mini"],
    "Land-Rover":    ["land rover", "land-rover"],
    "Porsche":       ["porsche"],
    "Jaguar":        ["jaguar"],
}


# DNC — never scrape or include these brands (Spiffy KALI campaign rule).
# detect_brand_from_name only *fails to match* these (they're absent from
# BRAND_NAME_KEYWORDS), which let full-sitemap mode fall through to
# "Independent" and include them anyway. Actively exclude by name instead.
DNC_KEYWORDS = ["hyundai", "genesis"]


def is_dnc_brand(dealer_name: str) -> bool:
    name_lower = f" {dealer_name.lower()} "
    return any(kw in name_lower for kw in DNC_KEYWORDS)


def detect_brand_from_name(dealer_name: str) -> str:
    """Return the first renowned brand found in the dealer name, or '' if none."""
    name_lower = f" {dealer_name.lower()} "
    for brand, keywords in BRAND_NAME_KEYWORDS.items():
        if any(kw in name_lower for kw in keywords):
            return brand
    return ""

# State abbr → DealerRater listing-page URL state name
STATE_URL_NAMES: dict[str, str] = {
    "AK": "Alaska",        "AZ": "Arizona",       "CA": "California",
    "CO": "Colorado",      "HI": "Hawaii",         "ID": "Idaho",
    "MN": "Minnesota",     "MT": "Montana",        "ND": "North-Dakota",
    "NM": "New-Mexico",    "NV": "Nevada",         "OR": "Oregon",
    "SD": "South-Dakota",  "UT": "Utah",           "WA": "Washington",
    "WY": "Wyoming",       "AL": "Alabama",        "AR": "Arkansas",
    "FL": "Florida",       "GA": "Georgia",        "IA": "Iowa",
    "KS": "Kansas",        "KY": "Kentucky",       "LA": "Louisiana",
    "MO": "Missouri",      "MS": "Mississippi",    "NE": "Nebraska",
    "OK": "Oklahoma",      "SC": "South-Carolina", "TN": "Tennessee",
    "TX": "Texas",         "CT": "Connecticut",    "DC": "DC",
    "DE": "Delaware",      "IL": "Illinois",       "IN": "Indiana",
    "MA": "Massachusetts", "MD": "Maryland",       "ME": "Maine",
    "MI": "Michigan",      "NH": "New-Hampshire",  "NJ": "New-Jersey",
    "NY": "New-York",      "NC": "North-Carolina", "OH": "Ohio",
    "PA": "Pennsylvania",  "RI": "Rhode-Island",   "VT": "Vermont",
    "VA": "Virginia",      "WI": "Wisconsin",
}


def build_session() -> requests.Session:
    s = requests.Session()
    s.headers.update(HEADERS)
    return s


# ── Sitemap mode ───────────────────────────────────────────────────────────────

def fetch_sitemap_urls(session: requests.Session) -> list[str]:
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
    keywords = OEM_KEYWORDS.get(oem, [oem.lower()])
    matched = [u for u in urls if any(kw in u.lower() for kw in keywords)]
    log.info("%s: %d URLs matched in sitemap", oem, len(matched))
    return matched


# ── Listing mode ───────────────────────────────────────────────────────────────

def fetch_listing_dealer_urls(
    session: requests.Session,
    brand: str,
    state_abbr: str,
    exclude_urls: set[str],
) -> list[str]:
    """
    Paginate through DealerRater's brand+state listing pages and return
    all dealer URLs not already in exclude_urls.
    """
    state_name = STATE_URL_NAMES.get(state_abbr)
    if not state_name:
        log.warning("No URL name mapped for state %s — skipping", state_abbr)
        return []

    brand_slug = brand.replace(" ", "-")
    base_url = f"https://www.dealerrater.com/car-dealers/{brand_slug}-dealer/{state_name}/"

    found: list[str] = []
    page = 1

    while True:
        url = base_url if page == 1 else f"{base_url}?page={page}"
        html = _safe_get(session, url, rate_limit=config.RATE_LIMIT_LISTING)
        if not html:
            break

        page_urls = _extract_dealer_urls(html)
        if not page_urls:
            log.debug("%s / %s page %d: no dealer URLs found", brand, state_abbr, page)
            break

        added = 0
        for u in page_urls:
            if u not in exclude_urls:
                found.append(u)
                added += 1

        log.debug("%s / %s page %d: %d URLs, %d new", brand, state_abbr, page, len(page_urls), added)

        soup = BeautifulSoup(html, "lxml")
        if not soup.select_one("a[rel='next']"):
            break
        page += 1

    return found


def _extract_dealer_urls(html: str) -> list[str]:
    """Pull all /dealer/ links from a listing page, deduplicated and normalised."""
    soup = BeautifulSoup(html, "lxml")
    seen: set[str] = set()
    urls: list[str] = []
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if "/dealer/" not in href or "dealer-reviews" not in href:
            continue
        full = href if href.startswith("http") else "https://www.dealerrater.com" + href
        clean = full.split("?")[0].rstrip("/") + "/"
        if clean not in seen:
            seen.add(clean)
            urls.append(clean)
    return urls


# ── Detail page ────────────────────────────────────────────────────────────────

def scrape_dealer_page(session: requests.Session, url: str) -> Optional[dict]:
    html = _safe_get(session, url)
    if not html:
        return None

    soup = BeautifulSoup(html, "lxml")
    data = _parse_json_ld(soup)

    dealer_name = (
        data.get("name")
        or _text(soup, "h1.dealer-name, h1.dealership-name, h1")
    )
    if not dealer_name or "error" in dealer_name.lower():
        return None

    address = data.get("address", {})
    city  = address.get("addressLocality") or _text(soup, ".city, [class*='city']")
    state = address.get("addressRegion")   or _text(soup, ".state, [class*='state']")

    if not city or not state:
        addr_text = _text(soup, ".dealer-address, [class*='address'], address")
        if addr_text and "," in addr_text:
            parts = addr_text.split(",")
            if not city:
                city = parts[-2].strip() if len(parts) >= 2 else ""
            if not state:
                state_zip = parts[-1].strip().split()
                state = state_zip[0] if state_zip else ""

    rating = (
        data.get("aggregateRating", {}).get("ratingValue")
        or _text(soup, "[class*='rating-static'], [class*='star-rating'], [itemprop='ratingValue']")
    )

    review_count_raw = (
        str(data.get("aggregateRating", {}).get("reviewCount", ""))
        or _text(soup, "[class*='review-count'], [itemprop='reviewCount']")
    )
    review_count = _parse_int(review_count_raw)

    phone_el = soup.select_one("a[href^='tel:'], [class*='phone']")
    phone = ""
    if phone_el:
        href = phone_el.get("href", "")
        phone = href.replace("tel:", "").strip() if href.startswith("tel:") else phone_el.get_text(strip=True)

    website = data.get("url") or ""
    if not website:
        for a in soup.find_all("a", href=True):
            href = a["href"]
            if href.startswith("http") and "dealerrater" not in href and "dealerrater" not in a.get_text().lower():
                website = href
                break

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


# ── Internal helpers ───────────────────────────────────────────────────────────

def _parse_json_ld(soup: BeautifulSoup) -> dict:
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


def _safe_get(
    session: requests.Session,
    url: str,
    rate_limit: float = config.RATE_LIMIT_DETAIL,
) -> Optional[str]:
    for attempt in range(config.MAX_RETRIES):
        try:
            r = session.get(url, timeout=25)
            r.raise_for_status()
            time.sleep(rate_limit + random.uniform(0, 0.5))
            return r.text
        except Exception as exc:
            wait = 2 ** attempt
            log.warning("Attempt %d/%d failed for %s: %s. Retry in %ds",
                        attempt + 1, config.MAX_RETRIES, url, exc, wait)
            time.sleep(wait)
    log.error("All retries exhausted: %s", url)
    return None
