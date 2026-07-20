#!/usr/bin/env python3
"""
Multi-signal verification for AI-Ark results — a company `industry` tag alone
is not trustworthy (confirmed via pilot: warranty vendors, R&D labs, and
university racing clubs all get tagged "motor vehicle manufacturing" same as
real dealers). A record is only kept if it passes ALL of:
  1. Company name contains an OEM brand as a whole word
  2. Company type is not public/nonprofit/government/educational
  3. Company name does not match a non-dealer exclusion pattern
  4. Person's title (re-checked locally, not trusted from the API) contains
     an exact ICP phrase
"""
import re
from urllib.parse import urlparse

from config import OEM_BRANDS, ICP_TITLE_PHRASES

# Brands with no active/relevant US franchise-dealer network for this
# campaign (discontinued in the US, or — Tesla — not sold through a
# traditional franchise/service-manager dealer model). Every sampled hit
# for these in a live pull was a false positive.
DROP_BRANDS = {"smart", "tesla", "scion", "saab", "suzuki"}

_BRAND_PATTERNS = [
    (b, re.compile(r"(?<![A-Za-z0-9])" + re.escape(b).replace(r"\ ", r"[\s-]") + r"(?![A-Za-z0-9])", re.I))
    for b in OEM_BRANDS
]

# Non-dealer business patterns that share brand-name words with real dealers.
EXCLUDE_NAME_PATTERNS = [
    r"\barchitect", r"\blaw\b", r"\blegal\b", r"\battorney", r"\bhospital\b",
    r"\brehabilitation\b", r"\bmedical center\b", r"\bresearch institute\b",
    r"\bresearch\b", r"\bmaterial handling\b", r"\bsupply chain\b",
    r"\blogistics\b", r"\bconstruction\b", r"\baviation\b", r"\baerospace\b",
    r"\bdefense\b", r"\bmining\b", r"\bmachinery\b", r"\btransportation\b(?!.*dealer)",
    r"\bmental health\b", r"\buniversity\b", r"\bcollege\b", r"\b(?:formula\s*)?sae\b",
    r"\bracing team\b", r"\brecycling\b", r"\bsalvage\b", r"\bjunk\s*yard\b",
    r"\bused\s+.*\bparts\b", r"\bwarranty\b", r"\bmobility\b", r"\binsurance\b",
    r"\bdonut", r"\bbakery\b", r"\bfoundation\b", r"\bchurch\b", r"\bschool\b",
    r"\bconsulting\b(?!.*dealer)", r"\bstaffing\b", r"\bfinancial services\b",
    r"\bcapital\b", r"\bventure\b", r"\brealty\b", r"\breal estate\b",
    # Expanded after auditing collected results — brand words colliding with
    # unrelated companies (Bentley Mills, Lincoln Electric, Tesla Solutions,
    # Jaguar Transport Holdings, Jeep Tours, Mitsubishi Chemical, etc.)
    r"\belectric(al)?\b", r"\bavenue communities\b", r"\bmills\b", r"\bpackaging\b",
    r"\bgallery\b", r"\bchemical\b", r"\bcement\b", r"group of america",
    r"\bwireless\b", r"\bathletics\b", r"strategic solutions", r"technical services",
    r"\btours?\b", r"\brafting\b", r"wealth management", r"finance of america",
    r"\bunderwrit", r"office equipment", r"manufactur", r"\bholdings\b",
    r"fueling services", r"heating and air", r"heating,?\s*cooling", r"\bplumbing\b",
    r"precision machine", r"\bbank of\b", r"\brecyclers?\b", r"\bwinery\b",
    r"\bvineyards\b", r"public affairs", r"\bwarehouse\b", r"\bsolar\b",
    r"moving\s*(and|&)?\s*storage", r"\bstorage\b", r"\bmover\b", r"\bsoftware\b",
    r"information flow", r"\bnetworks?\b", r"\btherapy\b", r"\bdwellings\b",
    r"post sound", r"\bhealthcare\b", r"\bresort\b", r"(and|&)\s*associates",
    r"\bmini\s*mart\b", r"\bconvenience store\b", r"\bmini\s*storage\b",
    r"\bmini\s*golf\b", r"\bthe\s+\w+\s+guy\b",
]
_EXCLUDE_RE = re.compile("|".join(EXCLUDE_NAME_PATTERNS), re.I)

EXCLUDE_TYPES = {"PUBLIC_COMPANY", "NON_PROFIT", "GOVERNMENT_AGENCY", "EDUCATIONAL"}


def detect_brand(company_name: str) -> str:
    """Return the OEM brand matched in the company name, or '' if none."""
    if not company_name:
        return ""
    for brand, pattern in _BRAND_PATTERNS:
        if pattern.search(company_name):
            return brand
    return ""


# Brands so generic (common surname/product/place word) that name-based
# exclusion alone still lets heavy noise through (WillScot Mobile Mini,
# Lincoln Surveying, Mini Melts USA, Lincoln Benefit Life, etc. — confirmed
# by direct sampling). Require the company's own industry tag to be
# automotive-shaped as an additional, brand-specific signal for just these.
STRICT_INDUSTRY_BRANDS = {"lincoln", "mini"}
_AUTO_INDUSTRIES = {"motor vehicle manufacturing", "retail", "automotive"}


# "Ram" is sold almost exclusively alongside Dodge/Chrysler/Jeep at the same
# franchise — real standalone "Ram ___" dealer names are rare, while dozens
# of unrelated companies (Ram Jack foundation repair, Ram Steelco, Ram
# Windows, Ram Aircraft, Ram Welding, ...) matched on the bare word. Require
# a companion signal.
_RAM_COMPANION_RE = re.compile(
    r"\b(dodge|chrysler|jeep|cdjr|truck|auto|motors?|dealer(ship)?)\b", re.I
)


def is_real_dealer(company_name: str, company_type: str, brand: str, industry: str = "") -> bool:
    if not company_name or not brand:
        return False
    if brand.lower() in DROP_BRANDS:
        return False
    if company_type and company_type.upper() in EXCLUDE_TYPES:
        return False
    if _EXCLUDE_RE.search(company_name):
        return False
    if brand.lower() in STRICT_INDUSTRY_BRANDS and (industry or "").lower() not in _AUTO_INDUSTRIES:
        return False
    if brand.lower() == "ram" and not _RAM_COMPANION_RE.search(company_name):
        return False
    return True


def matches_icp_title(title: str) -> bool:
    if not title:
        return False
    t = title.lower()
    if any(phrase in t for phrase in ICP_TITLE_PHRASES):
        return True
    # Common abbreviations the phrase list misses
    if re.search(r"(?<![a-z])gm(?![a-z])", t) or re.search(r"(?<![a-z])vp(?![a-z])", t):
        return True
    return False


def clean_domain(url: str) -> str:
    if not url:
        return ""
    url = url.strip()
    if not url:
        return ""
    if not url.startswith("http"):
        url = "http://" + url
    try:
        netloc = urlparse(url).netloc.lower()
    except Exception:
        return ""
    return re.sub(r"^www\.", "", netloc)


def extract_valid_email(email_field: dict) -> str:
    if not email_field:
        return ""
    for out in email_field.get("output") or []:
        if out.get("status") == "VALID" and out.get("address"):
            return out["address"]
    return ""
