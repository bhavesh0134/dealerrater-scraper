#!/usr/bin/env python3
"""
DealerRater Scraper — Spiffy KALI Campaign
==========================================
Scrapes franchised car dealership listings from DealerRater.com.
Outputs a clean CSV ready for AI-ARK contact enrichment.

Usage:
    # Probe one combo to verify selectors (always run first):
    python main.py --probe --oem Ford --state Texas

    # Scrape a single combo:
    python main.py --oem Ford --state Texas

    # Scrape all Tier 1 combos:
    python main.py --tier 1

    # Scrape everything:
    python main.py --tier all

Requirements:
    pip install playwright beautifulsoup4 lxml
    python -m playwright install chromium
"""

import argparse
import asyncio
import csv
import json
import logging
import os
import sys
from dataclasses import dataclass, fields, asdict
from io import TextIOWrapper
from typing import Optional

import config
from scraper import DealerRaterScraper
import parser as dr_parser

# ── Logging ────────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("main")


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
def open_csv_writer(
    output_path: str, append: bool = False
) -> tuple[TextIOWrapper, csv.DictWriter]:
    field_names = [f.name for f in fields(DealerRecord)]
    mode = "a" if append else "w"
    fh = open(output_path, mode, newline="", encoding="utf-8")
    writer = csv.DictWriter(fh, fieldnames=field_names)
    if not append:
        writer.writeheader()
    return fh, writer


# ── Checkpoint helpers ─────────────────────────────────────────────────────────
def _load_checkpoint(path: str) -> set[str]:
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            return set(json.load(f))
    return set()


def _save_checkpoint(path: str, done: set[str]) -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(sorted(done), f)


# ── Scraping logic ─────────────────────────────────────────────────────────────
async def scrape_combo(
    scraper: DealerRaterScraper,
    oem: str,
    state: str,
    writer: csv.DictWriter,
    fh: TextIOWrapper,
) -> int:
    """Scrape all pages for one OEM+state combo. Returns record count written."""
    url = f"https://www.dealerrater.com/dealer-reviews/{oem}-dealer/{state}/"
    written = 0
    page_num = 1

    while url:
        log.info("  %s | %s | page %d", oem, state, page_num)
        html = await scraper.fetch_listing_page(url)
        if not html:
            log.warning("  Failed to fetch listing page %d for %s/%s", page_num, oem, state)
            break

        stubs, next_url = dr_parser.parse_listing_page(html)
        if not stubs:
            log.info("  No dealers found on page %d — stopping.", page_num)
            break

        log.info("  Found %d dealers on page %d", len(stubs), page_num)

        for stub in stubs:
            detail: dict = {}
            if stub.get("dealer_url"):
                detail_html = await scraper.fetch_detail_page(stub["dealer_url"])
                if detail_html:
                    detail = dr_parser.parse_detail_page(detail_html)
                else:
                    log.debug("  Could not fetch detail page: %s", stub["dealer_url"])

            record = DealerRecord(
                dealer_name      = stub.get("dealer_name", ""),
                city             = stub.get("city", ""),
                state            = stub.get("state", ""),
                rating           = stub.get("rating", ""),
                review_count     = stub.get("review_count", 0),
                website          = detail.get("website", ""),
                phone            = detail.get("phone", ""),
                icp_staff_names  = detail.get("icp_staff_names", ""),
                icp_staff_titles = detail.get("icp_staff_titles", ""),
                dealer_url       = stub.get("dealer_url", ""),
                oem_brand        = oem,
                copy_variant     = config.OEM_VARIANT.get(oem, ""),
                assigned_rep     = config.get_rep(state),
                profile_type     = "Launcher",
                high_volume      = stub.get("review_count", 0) >= config.HIGH_VOLUME_THRESHOLD,
            )
            writer.writerow(asdict(record))
            fh.flush()
            written += 1

        url = next_url
        page_num += 1

    return written


async def async_main(
    combos: list[tuple[str, str]],
    checkpoint_path: str,
    fh: TextIOWrapper,
    writer: csv.DictWriter,
    done_combos: set[str],
) -> None:
    async with DealerRaterScraper() as scraper:
        for oem, state in combos:
            key = f"{oem}|{state}"
            if key in done_combos:
                log.info("Skipping %s (already done)", key)
                continue
            log.info("Scraping %s ...", key)
            n = await scrape_combo(scraper, oem, state, writer, fh)
            done_combos.add(key)
            _save_checkpoint(checkpoint_path, done_combos)
            log.info("%s: %d records written", key, n)


# ── Probe mode ─────────────────────────────────────────────────────────────────
async def run_probe(oem: str, state: str) -> None:
    """Dump raw HTML snippets to help tune parser.SELECTORS."""
    listing_url = f"https://www.dealerrater.com/dealer-reviews/{oem}-dealer/{state}/"
    print(f"\n{'='*70}")
    print(f"PROBE: {oem} | {state}")
    print(f"{'='*70}\n")

    async with DealerRaterScraper() as scraper:
        # Listing page
        print(f"[LISTING] {listing_url}\n")
        html = await scraper.fetch_raw(listing_url)
        if html:
            print(html[:4000])
            print("\n... (truncated) ...\n")

            # Try to get one detail URL
            stubs, _ = dr_parser.parse_listing_page(html)
            if stubs and stubs[0].get("dealer_url"):
                detail_url = stubs[0]["dealer_url"]
                print(f"\n[DETAIL] {detail_url}\n")
                detail_html = await scraper.fetch_raw(detail_url)
                if detail_html:
                    print(detail_html[:4000])
                    print("\n... (truncated) ...\n")
                else:
                    print("  (detail fetch failed)")
            else:
                print("  (no dealer_url found in listing — selectors may need updating)")
        else:
            print("  (listing fetch failed)")


# ── Dedup + merge ──────────────────────────────────────────────────────────────
def merge_and_dedup(raw_path: str, final_path: str) -> None:
    if not os.path.exists(raw_path):
        log.warning("Raw CSV not found: %s", raw_path)
        return

    seen: dict[str, dict] = {}
    with open(raw_path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            key = row.get("dealer_url") or row.get("dealer_name", "") + "|" + row.get("city", "")
            seen[key] = row  # last OEM scraped wins

    os.makedirs(os.path.dirname(final_path) or ".", exist_ok=True)
    rows = list(seen.values())
    if not rows:
        log.warning("No rows to write to final CSV.")
        return

    with open(final_path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)

    log.info("Deduplicated %d raw rows → %d unique dealers → %s",
             _count_rows(raw_path), len(rows), final_path)


def _count_rows(path: str) -> int:
    with open(path, newline="", encoding="utf-8") as f:
        return sum(1 for _ in csv.DictReader(f))


# ── CLI ────────────────────────────────────────────────────────────────────────
def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Scrape DealerRater for Spiffy KALI lead list.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  python main.py --probe --oem Ford --state Texas\n"
            "  python main.py --oem Ford --state Texas\n"
            "  python main.py --tier 1\n"
            "  python main.py --tier all\n"
        ),
    )
    p.add_argument("--tier", choices=["1", "2", "all"], default="1",
                   help="Which tier of OEM/state combos to scrape (default: 1)")
    p.add_argument("--oem",   help="Scrape a single OEM (e.g. Ford). Overrides --tier.")
    p.add_argument("--state", help="Scrape a single state (e.g. Texas). Use with --oem.")
    p.add_argument("--probe", action="store_true",
                   help="Dump raw HTML for selector debugging, then exit.")
    p.add_argument("--output-dir", default="output",
                   help="Base output directory (default: output/)")
    p.add_argument("--debug", action="store_true", help="Enable DEBUG logging.")
    return p.parse_args()


def build_combos(args: argparse.Namespace) -> list[tuple[str, str]]:
    if args.oem and args.state:
        return [(args.oem, args.state)]
    if args.oem:
        all_combos = config.TIER_1 + config.TIER_2
        return [(o, s) for o, s in all_combos if o == args.oem]
    if args.tier == "1":
        return config.TIER_1
    if args.tier == "2":
        return config.TIER_2
    return config.TIER_1 + config.TIER_2


# ── Entry point ────────────────────────────────────────────────────────────────
def main() -> None:
    args = parse_args()
    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)

    out_dir        = args.output_dir
    raw_path       = os.path.join(out_dir, "raw", "dealerrater_raw.csv")
    final_path     = os.path.join(out_dir, "final", "dealerrater_final.csv")
    checkpoint_path = os.path.join(out_dir, ".checkpoint.json")

    os.makedirs(os.path.join(out_dir, "raw"),   exist_ok=True)
    os.makedirs(os.path.join(out_dir, "final"), exist_ok=True)

    # ── Probe mode ─────────────────────────────────────────────────────────────
    if args.probe:
        oem   = args.oem   or "Ford"
        state = args.state or "Texas"
        asyncio.run(run_probe(oem, state))
        sys.exit(0)

    # ── Normal run ─────────────────────────────────────────────────────────────
    combos = build_combos(args)
    if not combos:
        log.error("No combos matched the given --oem / --state / --tier arguments.")
        sys.exit(1)

    done_combos = _load_checkpoint(checkpoint_path)
    remaining   = [(o, s) for o, s in combos if f"{o}|{s}" not in done_combos]
    log.info("Combos: %d total, %d already done, %d to scrape",
             len(combos), len(done_combos), len(remaining))

    append_mode = bool(done_combos) and os.path.exists(raw_path)
    fh, writer  = open_csv_writer(raw_path, append=append_mode)

    try:
        asyncio.run(async_main(combos, checkpoint_path, fh, writer, done_combos))
    finally:
        fh.close()
        _save_checkpoint(checkpoint_path, done_combos)

    merge_and_dedup(raw_path, final_path)
    log.info("Done. Final CSV: %s", final_path)


if __name__ == "__main__":
    main()
