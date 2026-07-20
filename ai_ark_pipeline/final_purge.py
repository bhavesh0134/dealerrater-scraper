#!/usr/bin/env python3
"""Purge rows failing either the Ram-companion rule or the description audit."""
import argparse
import csv
import os

from filters import _RAM_COMPANION_RE
from audit_descriptions import load_companies, classify


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw-dir", default=None)
    ap.add_argument("files", nargs="*",
                     default=["garrison_final.csv", "justin_final.csv", "mike_final.csv"])
    args = ap.parse_args()

    companies = load_companies(args.raw_dir)

    for fname in args.files:
        if not os.path.exists(fname):
            print(f"(skip {fname}: not found)")
            continue
        with open(fname, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            fieldnames = reader.fieldnames
            rows = list(reader)

        kept = []
        dropped_ram = 0
        dropped_desc = 0
        for r in rows:
            if r["oem_brand"].lower() == "ram" and not _RAM_COMPANION_RE.search(r["dealer_name"]):
                dropped_ram += 1
                continue
            status, _ = classify(r["website"], companies)
            if status == "FLAGGED_NON_DEALER":
                dropped_desc += 1
                continue
            kept.append(r)

        with open(fname, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=fieldnames)
            w.writeheader()
            w.writerows(kept)

        print(f"{fname}: {len(rows)} -> {len(kept)} "
              f"(dropped: ram_no_companion={dropped_ram}, flagged_non_dealer={dropped_desc})")


if __name__ == "__main__":
    main()
