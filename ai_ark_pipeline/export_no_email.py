#!/usr/bin/env python3
"""
Export every person who passed all the same quality filters (real dealer,
ICP title, in-territory, not already used for Spiffy) but where AI-Ark
could not verify a deliverable email — for enrichment in Clay.

Scans every raw email_finder_results page fetched this session, not just
the ones already processed into *_final.csv.
"""
import argparse
import csv
import json
import os

from config import REP_STATES, REP_DISPLAY_NAME
from filters import detect_brand, is_real_dealer, matches_icp_title, clean_domain
from process_results import load_used_domains
from audit_descriptions import load_companies, classify
from raw_data import email_finder_files

STATE_TO_REP = {}
for rep, states in REP_STATES.items():
    for s in states:
        STATE_TO_REP[s.lower()] = rep

FIELDNAMES = [
    "contact_name", "title", "dealer_name", "city", "state", "website",
    "oem_brand", "linkedin", "assigned_rep", "email_status",
]


def already_has_valid_email(email_field: dict) -> bool:
    for out in (email_field or {}).get("output") or []:
        if out.get("status") == "VALID" and out.get("address"):
            return True
    return False


def email_status_label(email_field: dict) -> str:
    outputs = (email_field or {}).get("output") or []
    if not outputs:
        return "not_searched"
    statuses = {o.get("status") for o in outputs}
    if "VALID" in statuses:
        return "valid"  # shouldn't happen here, safety
    return "/".join(sorted(s for s in statuses if s)) or "unknown"


def load_existing_linkedins(with_email_files):
    existing = set()
    for fname in with_email_files:
        if not os.path.exists(fname):
            continue
        with open(fname, newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                li = (row.get("linkedin") or "").strip().lower()
                if li:
                    existing.add(li)
    return existing


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw-dir", default=None)
    ap.add_argument("--used-domains", default="used_domains.txt")
    ap.add_argument("--with-email-files", nargs="*",
                     default=["garrison_final.csv", "justin_final.csv", "mike_final.csv"],
                     help="Already-exported with-email CSVs to dedupe against")
    args = ap.parse_args()

    used_domains = load_used_domains(args.used_domains)
    existing_linkedins = load_existing_linkedins(args.with_email_files)
    company_desc = load_companies(args.raw_dir)

    per_rep_rows = {rep: {} for rep in REP_STATES}  # keyed by linkedin/id for dedup
    files = email_finder_files(args.raw_dir)
    print(f"Scanning {len(files)} raw result files...")

    for path in files:
        try:
            with open(path) as f:
                data = json.load(f)
        except Exception:
            continue

        for item in data.get("content", []):
            profile = item.get("profile", {}) or {}
            company = item.get("company", {}) or {}
            summary = company.get("summary", {}) or {}
            link_c = company.get("link", {}) or {}
            loc = item.get("location", {}) or {}
            link_p = item.get("link", {}) or {}

            email_field = item.get("email")
            if already_has_valid_email(email_field):
                continue  # already in the with-email CSVs

            company_name = summary.get("name", "")
            company_type = summary.get("type", "")
            company_industry = summary.get("industry", "")
            domain = link_c.get("domain") or clean_domain(link_c.get("website", ""))

            brand = detect_brand(company_name)
            if not is_real_dealer(company_name, company_type, brand, company_industry):
                continue

            title = profile.get("title") or ""
            if not matches_icp_title(title):
                continue

            state = (loc.get("state") or "").strip()
            rep = STATE_TO_REP.get(state.lower())
            if not rep:
                continue  # out of territory / unresolvable state

            if domain and domain in used_domains:
                continue

            # Same description-level audit used for the email-verified list
            status, _ = classify(domain, company_desc) if domain else ("NO_DATA", "")
            if status == "FLAGGED_NON_DEALER":
                continue

            linkedin = link_p.get("linkedin", "") or ""
            dedup_key = linkedin.lower() or f"{profile.get('full_name','')}|{company_name}".lower()
            if dedup_key in existing_linkedins:
                continue

            bucket = per_rep_rows[rep]
            if dedup_key in bucket:
                continue

            bucket[dedup_key] = {
                "contact_name": profile.get("full_name", ""),
                "title": title,
                "dealer_name": company_name,
                "city": loc.get("city") or "",
                "state": state,
                "website": domain,
                "oem_brand": brand,
                "linkedin": linkedin,
                "assigned_rep": REP_DISPLAY_NAME.get(rep, rep),
                "email_status": email_status_label(email_field),
            }

    for rep, bucket in per_rep_rows.items():
        out_path = f"{rep}_no_email.csv"
        with open(out_path, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=FIELDNAMES)
            w.writeheader()
            w.writerows(bucket.values())
        print(f"{out_path}: {len(bucket)} contacts (no verified email)")


if __name__ == "__main__":
    main()
