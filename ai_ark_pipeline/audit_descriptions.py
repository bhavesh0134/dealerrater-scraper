#!/usr/bin/env python3
"""
Classify every dealer domain by actual company description/overview/SEO
text (not just name pattern) — per user request to verify at the
individual-contact level that these are genuine new-car dealers.
"""
import argparse
import csv
import glob
import json
import os
import re

from raw_data import company_search_files

NEW_CAR_RE = re.compile(
    r"\bnew\s+(and\s+(pre[- ]?owned|used)\s+)?(ford|toyota|chevrolet|chevy|chrysler|"
    r"mercedes|jeep|honda|nissan|kia|gmc|dodge|ram|cadillac|subaru|volkswagen|vw|mazda|"
    r"bmw|mitsubishi|audi|lexus|acura|volvo|infiniti|buick|mini|land rover|porsche|"
    r"jaguar|lincoln|fiat|alfa romeo|maserati|ferrari|polestar|bentley|lamborghini|"
    r"aston martin|mclaren|isuzu|cars?|trucks?|vehicles?|suvs?)\b",
    re.I,
)
DEALER_WORD_RE = re.compile(r"\b(dealer|dealership)\b", re.I)
# Conservative — only strong, specific, low-collision phrases. Single
# ambiguous words (coffee, hospital, credit union, tire) were producing
# false positives on real dealers whose marketing copy just mentions them
# in passing (e.g. "we work tirelessly", "support the local hospital").
NON_DEALER_RE = re.compile(
    r"\b(law firm|practicing attorney|licensed attorney|architectural firm|"
    r"construction company|construction services|welding (services|company|inc)|"
    r"steel fabrication|garage door|helical pier|foundation repair|geothermal drilling|"
    r"freight (broker|company|services)|trucking company|health\s?insurance plan|"
    r"hospital and (rehabilitation|health)|federal credit union|"
    r"financial planning firm|cpa firm|bookkeeping (services|firm)|"
    r"home inspection (services|company)|merchant services provider|"
    r"pest control|catering (company|services)|hvac (company|services)|"
    r"heating and (air conditioning|cooling) company|pontoon boats?|"
    r"seed company|violin shop|donut shop|oyster farm|racing team|"
    r"research institute|material handling (equipment|solutions)|"
    r"supply chain (management|solutions)|precision (tool|machine) (shop|corp)|"
    r"printing (company|services)|photonics|networking solutions|"
    r"software development (company|firm)|solar (panels?|energy) (company|installation)|"
    r"aircraft (sales|leasing|charter)|aviation (services|charter)|aerospace manufacturing|"
    r"energy services|oil (and|&) gas|telecommunications company|"
    r"human resources outsourcing|hr outsourcing|payroll (services|processing)|"
    r"property management company|real estate (brokerage|acquisition)|"
    r"contract manufacturing|ems services|international productions?|production designer|"
    r"executive search|recruiting services|staffing agency|hotel supply|hotel supplies|"
    r"polycrystalline silicon|semiconductor (industry|manufacturing)|feature films?|"
    r"motion picture|construction network|data and analytics|"
    r"automotive (parts|components) (manufacturer|supplier)|"
    r"designing,? developing,? and manufacturing|venture capital)\b",
    re.I,
)


def load_companies(raw_dir=None):
    companies = {}
    for path in company_search_files(raw_dir):
        try:
            with open(path) as f:
                data = json.load(f)
        except Exception:
            continue
        for item in data.get("content", []):
            summary = item.get("summary", {})
            link = item.get("link", {})
            domain = link.get("domain", "")
            if not domain:
                continue
            text = " ".join(filter(None, [
                summary.get("description", ""),
                summary.get("overview", ""),
                summary.get("seo", ""),
                summary.get("name", ""),
            ]))
            companies[domain] = {
                "name": summary.get("name", ""),
                "text": text,
                "industry": summary.get("industry", ""),
            }
    return companies


def classify(domain, companies):
    c = companies.get(domain)
    if not c:
        return "NO_DATA", ""
    text = c["text"]
    if not text.strip():
        return "NO_DESCRIPTION", c["name"]
    if NON_DEALER_RE.search(text):
        return "FLAGGED_NON_DEALER", c["name"]
    if NEW_CAR_RE.search(text) or DEALER_WORD_RE.search(text):
        return "CONFIRMED_NEW_CAR_DEALER", c["name"]
    return "AMBIGUOUS", c["name"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw-dir", default=None,
                     help="Directory containing mcp-ai-ark-*.txt raw result files "
                          "(default: auto-detect most recently modified session dir)")
    ap.add_argument("files", nargs="*", default=["garrison_final.csv", "justin_final.csv", "mike_final.csv"],
                     help="CSVs to audit (must have a 'website' column)")
    args = ap.parse_args()

    companies = load_companies(args.raw_dir)
    print(f"Loaded descriptions for {len(companies)} companies\n")

    for fname in args.files:
        if not os.path.exists(fname):
            print(f"(skip {fname}: not found)")
            continue
        with open(fname, newline="", encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
        counts = {}
        flagged_rows = []
        for r in rows:
            status, name = classify(r["website"], companies)
            counts[status] = counts.get(status, 0) + 1
            r["_audit_status"] = status
            if status in ("FLAGGED_NON_DEALER",):
                flagged_rows.append((r["dealer_name"], r["website"], name))

        print(f"=== {fname} ({len(rows)} rows) ===")
        for k, v in sorted(counts.items(), key=lambda x: -x[1]):
            print(f"  {k}: {v}")
        print()

        # write audited CSV with status column for inspection
        out_path = fname.replace("_final.csv", "_audited.csv")
        with open(out_path, "w", newline="", encoding="utf-8") as f:
            fieldnames = list(rows[0].keys())
            w = csv.DictWriter(f, fieldnames=fieldnames)
            w.writeheader()
            w.writerows(rows)

        if flagged_rows:
            print(f"  Sample flagged (non-dealer) in {fname}:")
            for dn, dom, cn in flagged_rows[:15]:
                print(f"    {dn} ({dom})")
            print()


if __name__ == "__main__":
    main()
