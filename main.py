#!/usr/bin/env python3
"""
DealerRater Scraper — Spiffy KALI Campaign
==========================================
Three modes:

  sitemap (default)
    Download S3 sitemap → filter by brand keyword in URL slug → scrape details.

  full-sitemap
    Download S3 sitemap → skip known URLs → scrape ALL remaining dealer pages →
    detect brand from dealer name → keep only renowned-brand dealers in rep states.
    Catches multi-brand/generic-name dealers the sitemap mode misses.

  listing  [DEPRECATED — DealerRater listing pages are JS-rendered]

Usage:
    python main.py --rep garrison                        # sitemap mode, Garrison states
    python main.py --mode listing --rep garrison         # listing mode, Garrison states
    python main.py --mode listing --rep garrison \\
        --exclude-file known_urls.txt                    # skip already-scraped dealers
    python main.py --debug-url URL                       # single-URL debug
"""

import argparse
import csv
import json
import logging
import os
import sys
from dataclasses import dataclass, fields, asdict
from io import TextIOWrapper

import config
import scraper as dr_scraper

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("main")

# ── Rep territory state sets ───────────────────────────────────────────────────
GARRISON_STATES = {
    "AK", "AZ", "CA", "CO", "HI", "ID", "MN", "MT", "ND",
    "NM", "NV", "OR", "SD", "UT", "WA", "WY",
}
JUSTIN_STATES = {
    "AL", "AR", "FL", "GA", "IA", "KS", "KY", "LA", "MO",
    "MS", "NE", "OK", "SC", "TN", "TX",
}
MIKE_STATES = {
    "CT", "DC", "DE", "IL", "IN", "MA", "MD", "ME", "MI",
    "NH", "NJ", "NY", "NC", "OH", "PA", "RI", "VT", "VA", "WI",
}

REP_STATES: dict[str, set[str]] = {
    "garrison": GARRISON_STATES,
    "justin":   JUSTIN_STATES,
    "mike":     MIKE_STATES,
}

STATE_ABBR = {
    "alaska": "AK", "arizona": "AZ", "california": "CA", "colorado": "CO",
    "hawaii": "HI", "idaho": "ID", "minnesota": "MN", "montana": "MT",
    "north dakota": "ND", "new mexico": "NM", "nevada": "NV", "oregon": "OR",
    "south dakota": "SD", "utah": "UT", "washington": "WA", "wyoming": "WY",
    "alabama": "AL", "arkansas": "AR", "florida": "FL", "georgia": "GA",
    "iowa": "IA", "kansas": "KS", "kentucky": "KY", "louisiana": "LA",
    "missouri": "MO", "mississippi": "MS", "nebraska": "NE", "oklahoma": "OK",
    "south carolina": "SC", "tennessee": "TN", "texas": "TX",
    "connecticut": "CT", "dc": "DC", "district of columbia": "DC",
    "delaware": "DE", "illinois": "IL", "indiana": "IN",
    "massachusetts": "MA", "maryland": "MD", "maine": "ME", "michigan": "MI",
    "new hampshire": "NH", "new jersey": "NJ", "new york": "NY",
    "north carolina": "NC", "ohio": "OH", "pennsylvania": "PA",
    "rhode island": "RI", "vermont": "VT", "virginia": "VA", "wisconsin": "WI",
    "ak":"AK","az":"AZ","ca":"CA","co":"CO","hi":"HI","id":"ID","mn":"MN",
    "mt":"MT","nd":"ND","nm":"NM","nv":"NV","or":"OR","sd":"SD","ut":"UT",
    "wa":"WA","wy":"WY","al":"AL","ar":"AR","fl":"FL","ga":"GA","ia":"IA",
    "ks":"KS","ky":"KY","la":"LA","mo":"MO","ms":"MS","ne":"NE","ok":"OK",
    "sc":"SC","tn":"TN","tx":"TX","ct":"CT","dc":"DC","de":"DE","il":"IL",
    "in":"IN","ma":"MA","md":"MD","me":"ME","mi":"MI","nh":"NH","nj":"NJ",
    "ny":"NY","nc":"NC","oh":"OH","pa":"PA","ri":"RI","vt":"VT","va":"VA",
    "wi":"WI",
}


# ── Data model ─────────────────────────────────────────────────────────────────
@dataclass
class DealerRecord:
    dealer_name:      str  = ""
    city:             str  = ""
    state:            str  = ""
    rating:           str  = ""
    review_count:     int  = 0
    website:          str  = ""
    phone:            str  = ""
    icp_staff_names:  str  = ""
    icp_staff_titles: str  = ""
    dealer_url:       str  = ""
    oem_brand:        str  = ""
    copy_variant:     str  = ""
    assigned_rep:     str  = ""
    profile_type:     str  = ""
    high_volume:      bool = False


# ── CSV helpers ────────────────────────────────────────────────────────────────
def open_csv_writer(path: str, append: bool = False) -> tuple[TextIOWrapper, csv.DictWriter]:
    field_names = [f.name for f in fields(DealerRecord)]
    fh = open(path, "a" if append else "w", newline="", encoding="utf-8")
    writer = csv.DictWriter(fh, fieldnames=field_names)
    if not append:
        writer.writeheader()
    return fh, writer


# ── Checkpoint ─────────────────────────────────────────────────────────────────
def _load_checkpoint(path: str) -> set[str]:
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            return set(json.load(f))
    return set()


def _save_checkpoint(path: str, done: set[str]) -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(sorted(done), f)


# ── Exclude file (master list URLs) ───────────────────────────────────────────
def load_exclude_urls(path: str) -> set[str]:
    if not path or not os.path.exists(path):
        return set()
    with open(path, encoding="utf-8") as f:
        urls = {line.strip() for line in f if line.strip()}
    log.info("Loaded %d excluded URLs from %s", len(urls), path)
    return urls


# ── State helpers ──────────────────────────────────────────────────────────────
def _resolve_state_abbr(raw: str) -> str:
    return STATE_ABBR.get(raw.strip().lower(), "")


def _get_rep(abbr: str) -> str:
    if abbr in GARRISON_STATES: return "Garrison Ramoso"
    if abbr in JUSTIN_STATES:   return "Justin Smith"
    if abbr in MIKE_STATES:     return "Mike Arena"
    return ""


def _write_record(writer, data: dict, url: str, brand: str, state_abbr: str) -> None:
    record = DealerRecord(
        dealer_name      = data["dealer_name"],
        city             = data["city"],
        state            = state_abbr or data["state"],
        rating           = data["rating"],
        review_count     = data["review_count"],
        website          = data["website"],
        phone            = data["phone"],
        icp_staff_names  = data["icp_staff_names"],
        icp_staff_titles = data["icp_staff_titles"],
        dealer_url       = url,
        oem_brand        = brand,
        copy_variant     = config.OEM_VARIANT.get(brand, ""),
        assigned_rep     = _get_rep(state_abbr),
        profile_type     = "Launcher",
        high_volume      = data["review_count"] >= config.HIGH_VOLUME_THRESHOLD,
    )
    writer.writerow(asdict(record))


# ── Sitemap mode ───────────────────────────────────────────────────────────────
def run_scrape(
    oems: list[str],
    filter_states: set[str],
    out_dir: str,
    checkpoint_path: str,
    rep_name: str = "all",
) -> None:
    os.makedirs(os.path.join(out_dir, "raw"),   exist_ok=True)
    os.makedirs(os.path.join(out_dir, "final"), exist_ok=True)

    if oems and len(oems) > 5:
        brand_slug = f"{len(oems)}-net-new-brands"
    elif oems:
        brand_slug = "-".join(o.lower().replace("-", "").replace(" ", "") for o in oems)
    else:
        brand_slug = "all-brands"

    raw_path   = os.path.join(out_dir, "raw",   f"dealerrater_{brand_slug}_raw.csv")
    final_path = os.path.join(out_dir, "final", f"{rep_name}-{brand_slug}-master.csv")

    done = _load_checkpoint(checkpoint_path)
    session = dr_scraper.build_session()

    all_urls = dr_scraper.fetch_sitemap_urls(session)
    if not all_urls:
        log.error("Sitemap returned no URLs. Aborting.")
        sys.exit(1)

    work: list[tuple[str, str]] = []
    for oem in oems:
        urls = dr_scraper.filter_urls_by_brand(all_urls, oem)
        work.extend((oem, u) for u in urls)

    log.info("Total dealers to scrape: %d", len(work))

    append_mode = bool(done) and os.path.exists(raw_path)
    fh, writer = open_csv_writer(raw_path, append=append_mode)
    written = 0

    try:
        for i, (oem, url) in enumerate(work, 1):
            if url in done:
                continue

            data = dr_scraper.scrape_dealer_page(session, url)
            done.add(url)

            if not data:
                continue

            state_abbr = _resolve_state_abbr(data.get("state", ""))
            if filter_states and state_abbr not in filter_states:
                continue

            _write_record(writer, data, url, oem, state_abbr)
            fh.flush()
            written += 1

            if i % 50 == 0:
                _save_checkpoint(checkpoint_path, done)
                log.info("Progress: %d/%d scraped, %d kept", i, len(work), written)

    finally:
        fh.close()
        _save_checkpoint(checkpoint_path, done)

    log.info("Scrape complete. %d dealers written to %s", written, raw_path)
    _dedup(raw_path, final_path)


# ── Full-sitemap mode ──────────────────────────────────────────────────────────
def run_full_sitemap_scrape(
    filter_states: set[str],
    out_dir: str,
    checkpoint_path: str,
    rep_name: str,
    exclude_urls: set[str],
) -> None:
    """
    Scrape every dealer in the S3 sitemap that isn't already known.
    Detect the brand from the dealer's page name — catches multi-brand and
    generic-name dealers the slug-keyword filter misses.
    """
    os.makedirs(os.path.join(out_dir, "raw"),   exist_ok=True)
    os.makedirs(os.path.join(out_dir, "final"), exist_ok=True)

    raw_path   = os.path.join(out_dir, "raw",   f"fullsitemap_{rep_name}_raw.csv")
    final_path = os.path.join(out_dir, "final", f"{rep_name}-fullsitemap-net-new-master.csv")

    done = _load_checkpoint(checkpoint_path)
    known: set[str] = exclude_urls | done
    session = dr_scraper.build_session()

    all_urls = dr_scraper.fetch_sitemap_urls(session)
    if not all_urls:
        log.error("Sitemap returned no URLs. Aborting.")
        sys.exit(1)

    # Skip anything already known
    work = [u for u in all_urls if u not in known]
    log.info("Sitemap: %d total | %d already known | %d to scrape",
             len(all_urls), len(all_urls) - len(work), len(work))

    append_mode = bool(done) and os.path.exists(raw_path)
    fh, writer = open_csv_writer(raw_path, append=append_mode)
    written = 0

    try:
        for i, url in enumerate(work, 1):
            if url in done:
                continue

            data = dr_scraper.scrape_dealer_page(session, url)
            done.add(url)

            if not data:
                continue

            state_abbr = _resolve_state_abbr(data.get("state", ""))
            if filter_states and state_abbr not in filter_states:
                continue

            brand = dr_scraper.detect_brand_from_name(data["dealer_name"])
            if not brand:
                continue  # not a renowned-brand dealer

            _write_record(writer, data, url, brand, state_abbr)
            fh.flush()
            written += 1

            if i % 100 == 0:
                _save_checkpoint(checkpoint_path, done)
                log.info("Progress: %d/%d checked, %d renowned-brand dealers kept", i, len(work), written)

    finally:
        fh.close()
        _save_checkpoint(checkpoint_path, done)

    log.info("Scrape complete. %d net-new dealers written to %s", written, raw_path)
    _dedup(raw_path, final_path)


# ── Listing mode ───────────────────────────────────────────────────────────────
def run_listing_scrape(
    brands: list[str],
    filter_states: set[str],
    out_dir: str,
    checkpoint_path: str,
    rep_name: str,
    exclude_urls: set[str],
) -> None:
    os.makedirs(os.path.join(out_dir, "raw"),   exist_ok=True)
    os.makedirs(os.path.join(out_dir, "final"), exist_ok=True)

    raw_path   = os.path.join(out_dir, "raw",   f"listing_{rep_name}_raw.csv")
    final_path = os.path.join(out_dir, "final", f"{rep_name}-listing-net-new-master.csv")

    done = _load_checkpoint(checkpoint_path)
    # URLs to skip = master list + already scraped this run
    known: set[str] = exclude_urls | done
    session = dr_scraper.build_session()

    # Phase 1: collect all new dealer URLs from listing pages (brand × state)
    log.info("Phase 1: collecting dealer URLs from listing pages ...")
    work: list[tuple[str, str]] = []  # (brand, dealer_url)
    seen_in_work: set[str] = set()

    for state_abbr in sorted(filter_states):
        for brand in brands:
            new_urls = dr_scraper.fetch_listing_dealer_urls(session, brand, state_abbr, known)
            for u in new_urls:
                if u not in seen_in_work:
                    work.append((brand, u))
                    seen_in_work.add(u)
                    known.add(u)  # prevent same URL appearing under another brand
            log.info("  %s / %s: %d new URLs", brand, state_abbr, len(new_urls))

    log.info("Phase 1 done. %d net-new dealers to scrape.", len(work))

    # Phase 2: scrape each detail page
    log.info("Phase 2: scraping dealer detail pages ...")
    append_mode = bool(done) and os.path.exists(raw_path)
    fh, writer = open_csv_writer(raw_path, append=append_mode)
    written = 0

    try:
        for i, (brand, url) in enumerate(work, 1):
            if url in done:
                continue

            data = dr_scraper.scrape_dealer_page(session, url)
            done.add(url)

            if not data:
                continue

            state_abbr = _resolve_state_abbr(data.get("state", ""))
            if filter_states and state_abbr not in filter_states:
                continue

            _write_record(writer, data, url, brand, state_abbr)
            fh.flush()
            written += 1

            if i % 100 == 0:
                _save_checkpoint(checkpoint_path, done)
                log.info("Progress: %d/%d scraped, %d kept", i, len(work), written)

    finally:
        fh.close()
        _save_checkpoint(checkpoint_path, done)

    log.info("Scrape complete. %d net-new dealers written to %s", written, raw_path)
    _dedup(raw_path, final_path)


# ── Dedup ──────────────────────────────────────────────────────────────────────
def _dedup(raw_path: str, final_path: str) -> None:
    if not os.path.exists(raw_path):
        return
    seen: dict[str, dict] = {}
    with open(raw_path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            key = row.get("dealer_url") or (row.get("dealer_name", "") + "|" + row.get("city", ""))
            seen[key] = row
    rows = list(seen.values())
    if not rows:
        return
    with open(final_path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    log.info("Final CSV: %d unique dealers → %s", len(rows), final_path)


# ── CLI ────────────────────────────────────────────────────────────────────────
def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="DealerRater scraper — Spiffy KALI")
    p.add_argument("--mode", choices=["sitemap", "full-sitemap", "listing"], default="sitemap",
                   help="sitemap: keyword-filter on S3 sitemap (default). "
                        "full-sitemap: scrape ALL sitemap URLs, detect brand from dealer name.")
    p.add_argument("--oem", nargs="+", metavar="OEM",
                   help="One or more OEMs (sitemap mode). Default: all.")
    p.add_argument("--exclude-file", metavar="FILE",
                   help="Path to newline-delimited file of dealer URLs to skip (listing mode).")
    p.add_argument("--state", help="Single state abbreviation filter (e.g. CA).")
    p.add_argument("--rep", choices=["garrison", "justin", "mike"],
                   help="Filter by rep territory.")
    p.add_argument("--all-states", action="store_true",
                   help="No state filter — scrape all states.")
    p.add_argument("--output-dir", default="output")
    p.add_argument("--debug-url", help="Scrape a single URL and print the result, then exit.")
    p.add_argument("--debug", action="store_true")
    return p.parse_args()


def main() -> None:
    args = parse_args()
    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)

    if args.debug_url:
        session = dr_scraper.build_session()
        result = dr_scraper.scrape_dealer_page(session, args.debug_url)
        import pprint; pprint.pprint(result)
        return

    if args.all_states:
        filter_states: set[str] = set()
    elif args.state:
        filter_states = {args.state.upper()}
    elif args.rep:
        filter_states = REP_STATES[args.rep]
    else:
        filter_states = GARRISON_STATES

    checkpoint_path = os.path.join(args.output_dir, ".checkpoint.json")

    if args.mode == "full-sitemap":
        exclude_urls = load_exclude_urls(args.exclude_file or "")
        log.info("Mode: full-sitemap | Rep: %s | Excluded URLs: %d",
                 args.rep or "garrison", len(exclude_urls))
        run_full_sitemap_scrape(
            filter_states, args.output_dir,
            checkpoint_path, rep_name=args.rep or "garrison",
            exclude_urls=exclude_urls,
        )
    elif args.mode == "listing":
        exclude_urls = load_exclude_urls(args.exclude_file or "")
        brands = dr_scraper.RENOWNED_BRANDS
        log.info("Mode: listing | Rep: %s | Brands: %d | Excluded URLs: %d",
                 args.rep or "garrison", len(brands), len(exclude_urls))
        run_listing_scrape(
            brands, filter_states, args.output_dir,
            checkpoint_path, rep_name=args.rep or "garrison",
            exclude_urls=exclude_urls,
        )
    else:
        oems = args.oem if args.oem else list(dr_scraper.OEM_KEYWORDS.keys())
        log.info("Mode: sitemap | OEMs: %s | States: %s", oems, filter_states or "ALL")
        run_scrape(oems, filter_states, args.output_dir, checkpoint_path,
                   rep_name=args.rep or "all")


if __name__ == "__main__":
    main()
