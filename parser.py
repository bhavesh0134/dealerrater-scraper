#!/usr/bin/env python3
"""
HTML parsing for DealerRater listing and detail pages.
All selector strings live in SELECTORS — update here if the DOM changes.

⚠️  Run  python main.py --probe --oem Ford --state Texas  first to dump
    raw HTML and verify these selectors match the live site.
"""

import re
from bs4 import BeautifulSoup

import config

# ── Selectors ──────────────────────────────────────────────────────────────────
# Inspect the live DOM with --probe before a full run. These are best-effort
# guesses based on DealerRater's typical class naming conventions.
SELECTORS: dict[str, str] = {
    # Listing page — dealer cards
    "dealer_cards":       "div.dealer-review-listing",
    "dealer_name":        "span.dealership-name",
    "dealer_location":    "p.address",
    "dealer_rating":      "span.rating-static-indv",
    "dealer_review_count": "a.review-count",
    "dealer_link":        "a.review-count",        # href leads to detail page

    # Listing page — pagination
    "next_page":          "a[rel='next']",

    # Detail page
    "detail_phone":       "a.phone-number",
    "detail_website":     "a.website-link",
    "staff_section":      "div.employee-review-all",
    "staff_member":       "div.employee-review",
    "staff_name":         "span.employee-name",
    "staff_title":        "span.employee-title",
}

BASE_URL = "https://www.dealerrater.com"


# ── Listing page ───────────────────────────────────────────────────────────────
def parse_listing_page(html: str) -> tuple[list[dict], str | None]:
    """
    Returns (dealer_stubs, next_page_url).
    next_page_url is None when on the last page.
    Each stub: {dealer_name, city, state, rating, review_count, dealer_url}.
    """
    soup = BeautifulSoup(html, "lxml")
    cards = soup.select(SELECTORS["dealer_cards"])
    stubs: list[dict] = []

    for card in cards:
        stub = _parse_card(card)
        if stub.get("dealer_name"):
            stubs.append(stub)

    next_url = _parse_next_page(soup)
    return stubs, next_url


def _parse_card(card: BeautifulSoup) -> dict:
    stub: dict = {}

    # Name
    el = card.select_one(SELECTORS["dealer_name"])
    stub["dealer_name"] = el.get_text(strip=True) if el else ""

    # Location — "Houston, TX" → split into city / state
    loc_el = card.select_one(SELECTORS["dealer_location"])
    location = loc_el.get_text(strip=True) if loc_el else ""
    city, state = _split_location(location)
    stub["city"]  = city
    stub["state"] = state

    # Rating
    rating_el = card.select_one(SELECTORS["dealer_rating"])
    stub["rating"] = _parse_rating(rating_el.get_text(strip=True) if rating_el else "")

    # Review count
    rev_el = card.select_one(SELECTORS["dealer_review_count"])
    stub["review_count"] = _parse_review_count(rev_el.get_text(strip=True) if rev_el else "")

    # Detail URL — prefer the anchor on dealer name, fall back to review count link
    name_a = card.select_one("a.dealership-name, a.dealer-name")
    if not name_a:
        name_a = card.select_one(SELECTORS["dealer_link"])
    if name_a and name_a.get("href"):
        href = name_a["href"]
        stub["dealer_url"] = href if href.startswith("http") else BASE_URL + href
    else:
        stub["dealer_url"] = ""

    return stub


def _parse_next_page(soup: BeautifulSoup) -> str | None:
    el = soup.select_one(SELECTORS["next_page"])
    if el and el.get("href"):
        href = el["href"]
        return href if href.startswith("http") else BASE_URL + href
    return None


def _split_location(text: str) -> tuple[str, str]:
    """'Houston, TX' → ('Houston', 'TX').  Returns ('', '') on no match."""
    if "," in text:
        parts = text.split(",", 1)
        return parts[0].strip(), parts[1].strip()
    return text.strip(), ""


def _parse_rating(text: str) -> str:
    m = re.search(r"[\d]+\.?[\d]*", text)
    return m.group(0) if m else ""


def _parse_review_count(text: str) -> int:
    m = re.search(r"[\d,]+", text)
    if m:
        return int(m.group(0).replace(",", ""))
    return 0


# ── Detail page ────────────────────────────────────────────────────────────────
def parse_detail_page(html: str) -> dict:
    """
    Returns {phone, website, icp_staff_names, icp_staff_titles}.
    All fields default to empty string — CSV-safe.
    """
    soup = BeautifulSoup(html, "lxml")
    detail: dict = {}

    # Phone
    phone_el = soup.select_one(SELECTORS["detail_phone"])
    detail["phone"] = _clean_phone(phone_el.get_text(strip=True) if phone_el else "")

    # Website
    site_el = soup.select_one(SELECTORS["detail_website"])
    if site_el:
        href = site_el.get("href", "") or site_el.get_text(strip=True)
        detail["website"] = href.rstrip("/")
    else:
        detail["website"] = ""

    # ICP staff
    names, titles = _parse_icp_staff(soup)
    detail["icp_staff_names"]  = " | ".join(names)
    detail["icp_staff_titles"] = " | ".join(titles)

    return detail


def _parse_icp_staff(soup: BeautifulSoup) -> tuple[list[str], list[str]]:
    names: list[str] = []
    titles: list[str] = []

    section = soup.select_one(SELECTORS["staff_section"])
    candidates = section.select(SELECTORS["staff_member"]) if section else []

    # Fallback: scan whole page if dedicated section not found
    if not candidates:
        candidates = soup.select(SELECTORS["staff_member"])

    for member in candidates:
        name_el  = member.select_one(SELECTORS["staff_name"])
        title_el = member.select_one(SELECTORS["staff_title"])
        name  = name_el.get_text(strip=True)  if name_el  else ""
        title = title_el.get_text(strip=True) if title_el else ""
        if name and _is_icp_title(title):
            names.append(name)
            titles.append(title)

    return names, titles


def _is_icp_title(title: str) -> bool:
    t = title.lower()
    return any(kw in t for kw in config.ICP_TITLE_KEYWORDS)


def _clean_phone(text: str) -> str:
    return re.sub(r"[^\d()\-+. ]", "", text).strip()
