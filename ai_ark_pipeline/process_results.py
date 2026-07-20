#!/usr/bin/env python3
"""
Consume a raw email_finder_results JSON file (as saved to disk by the tool
when output is large) and append filtered, verified contact rows to a
per-rep CSV. Dedupes by email across repeated invocations.

Usage:
    python3 process_results.py <raw_json_path> <rep> <output_csv>
"""
import csv
import json
import os
import sys

from config import REP_DISPLAY_NAME
from filters import detect_brand, is_real_dealer, matches_icp_title, clean_domain, extract_valid_email

FIELDNAMES = [
    "contact_name", "title", "email", "dealer_name", "city", "state",
    "website", "oem_brand", "linkedin", "assigned_rep",
]


def load_used_domains(path="used_domains.txt"):
    if not os.path.exists(path):
        return set()
    with open(path) as f:
        return set(l.strip() for l in f if l.strip())


def load_existing_emails(csv_path):
    if not os.path.exists(csv_path):
        return set()
    with open(csv_path, newline="", encoding="utf-8") as f:
        return set(row["email"].lower() for row in csv.DictReader(f) if row.get("email"))


def process(raw_json_path, rep, output_csv):
    used_domains = load_used_domains(
        os.path.join(os.path.dirname(__file__), "used_domains.txt")
    )
    existing_emails = load_existing_emails(output_csv)

    with open(raw_json_path) as f:
        data = json.load(f)

    write_header = not os.path.exists(output_csv)
    kept = 0
    seen_this_batch = set()

    with open(output_csv, "a", newline="", encoding="utf-8") as out:
        writer = csv.DictWriter(out, fieldnames=FIELDNAMES)
        if write_header:
            writer.writeheader()

        for item in data.get("content", []):
            profile = item.get("profile", {})
            company = item.get("company", {}) or {}
            summary = company.get("summary", {}) or {}
            link = company.get("link", {}) or {}

            company_name = summary.get("name", "")
            company_type = summary.get("type", "")
            company_industry = summary.get("industry", "")
            domain = link.get("domain") or clean_domain(link.get("website", ""))

            brand = detect_brand(company_name)
            if not is_real_dealer(company_name, company_type, brand, company_industry):
                continue

            title = profile.get("title") or ""
            if not matches_icp_title(title):
                continue

            email = extract_valid_email(item.get("email"))
            if not email:
                continue
            email_l = email.lower()
            if email_l in existing_emails or email_l in seen_this_batch:
                continue

            if domain and domain in used_domains:
                continue

            loc = item.get("location", {}) or {}
            row = {
                "contact_name": profile.get("full_name", ""),
                "title": title,
                "email": email,
                "dealer_name": company_name,
                "city": loc.get("city") or "",
                "state": loc.get("state") or "",
                "website": domain,
                "oem_brand": brand,
                "linkedin": (item.get("link") or {}).get("linkedin", ""),
                "assigned_rep": REP_DISPLAY_NAME.get(rep, rep),
            }
            writer.writerow(row)
            seen_this_batch.add(email_l)
            kept += 1

    print(f"{raw_json_path}: kept {kept} new contacts -> {output_csv}")
    return kept


if __name__ == "__main__":
    raw_json_path, rep, output_csv = sys.argv[1], sys.argv[2], sys.argv[3]
    process(raw_json_path, rep, output_csv)
