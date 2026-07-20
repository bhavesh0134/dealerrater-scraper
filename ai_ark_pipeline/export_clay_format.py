#!/usr/bin/env python3
"""
Re-export the already-finalized contact lists (per-rep, with-email and
no-email) into the exact Clay-import column schema requested, pulling the
extra company/person fields back out of the raw AI-Ark JSON already on disk.
"""
import argparse
import csv
import json
import os

from raw_data import email_finder_files, company_search_files

HEADER = [
    "First Name", "Last Name", "Full Name", "Email", "LinkedIn Profile",
    "Job Title", "Company Name", "Website", "Domain", "Company LinkedIn",
    "Company Size", "No. of Employees", "Industry", "Company Description",
    "Company Primary Phone", "Company Founding Year", "Company Annual Revenue",
    "Company Total Funding", "Company Last Funding Type",
    "Company Last Funding Amount", "Company Last Funding Date", "OEM Brand",
    "Location", "City", "State", "Country", "Company Location", "Company City",
    "Company State", "Company Country",
]


def extract_valid_email(email_field):
    for out in (email_field or {}).get("output") or []:
        if out.get("status") == "VALID" and out.get("address"):
            return out["address"]
    return ""


def build_person_index(raw_dir=None):
    """linkedin_url -> raw item; also (name, company) -> raw item as fallback."""
    by_linkedin = {}
    by_name_company = {}
    for path in email_finder_files(raw_dir):
        try:
            with open(path) as f:
                data = json.load(f)
        except Exception:
            continue
        for item in data.get("content", []):
            li = ((item.get("link") or {}).get("linkedin") or "").strip().lower()
            name = (item.get("profile", {}).get("full_name") or "").strip().lower()
            cname = (item.get("company", {}).get("summary", {}).get("name") or "").strip().lower()
            if li and li not in by_linkedin:
                by_linkedin[li] = item
            key = (name, cname)
            if name and cname and key not in by_name_company:
                by_name_company[key] = item
    return by_linkedin, by_name_company


def build_company_index(raw_dir=None):
    """domain -> company summary object (from company_search results)."""
    by_domain = {}
    for path in company_search_files(raw_dir):
        try:
            with open(path) as f:
                data = json.load(f)
        except Exception:
            continue
        for item in data.get("content", []):
            domain = (item.get("link", {}) or {}).get("domain", "")
            if domain and domain not in by_domain:
                by_domain[domain] = item
    return by_domain


def company_field(company_obj, path, default=""):
    cur = company_obj
    for key in path:
        if not isinstance(cur, dict):
            return default
        cur = cur.get(key)
    return cur if cur not in (None, "") else default


def row_from_item(item, company_fallback, existing_row):
    profile = item.get("profile", {}) or {}
    company = item.get("company", {}) or {}
    summary = company.get("summary", {}) or {}
    link_c = company.get("link", {}) or {}
    fin = company.get("financial", {}) or {}
    loc_p = item.get("location", {}) or {}
    loc_c = company.get("location", {}).get("headquarter", {}) if company.get("location") else {}
    funding = fin.get("funding", {}) or {}
    link_p = item.get("link", {}) or {}

    domain = link_c.get("domain", "") or existing_row.get("website", "")

    # backfill from company_search index if this domain has richer data there
    cf = company_fallback.get(domain, {})
    cf_summary = cf.get("summary", {}) if cf else {}
    cf_link = cf.get("link", {}) if cf else {}
    cf_fin = cf.get("financial", {}) if cf else {}
    cf_loc = cf.get("location", {}).get("headquarter", {}) if cf.get("location") else {}

    staff = summary.get("staff") or cf_summary.get("staff") or {}
    staff_range = staff.get("range") or {}
    size_str = f"{staff_range.get('start','')}-{staff_range.get('end','')}" if staff_range else ""

    email = extract_valid_email(item.get("email")) or existing_row.get("email", "")

    return {
        "First Name": profile.get("first_name", ""),
        "Last Name": profile.get("last_name", ""),
        "Full Name": profile.get("full_name", "") or existing_row.get("contact_name", ""),
        "Email": email,
        "LinkedIn Profile": link_p.get("linkedin", "") or existing_row.get("linkedin", ""),
        "Job Title": profile.get("title", "") or existing_row.get("title", ""),
        "Company Name": summary.get("name") or cf_summary.get("name") or existing_row.get("dealer_name", ""),
        "Website": link_c.get("website") or cf_link.get("website", ""),
        "Domain": domain,
        "Company LinkedIn": link_c.get("linkedin") or cf_link.get("linkedin", ""),
        "Company Size": size_str,
        "No. of Employees": staff.get("total", ""),
        "Industry": summary.get("industry") or cf_summary.get("industry", ""),
        "Company Description": summary.get("description") or cf_summary.get("description", ""),
        "Company Primary Phone": (company.get("contact", {}) or {}).get("phone", {}).get("raw", "")
                                   or (cf.get("contact", {}) or {}).get("phone", {}).get("raw", ""),
        "Company Founding Year": summary.get("founded_year") or cf_summary.get("founded_year", ""),
        "Company Annual Revenue": (fin.get("revenue", {}) or {}).get("annual", {}).get("amount", "")
                                    or (cf_fin.get("revenue", {}) or {}).get("annual", {}).get("amount", ""),
        "Company Total Funding": funding.get("total_amount", ""),
        "Company Last Funding Type": funding.get("type", ""),
        "Company Last Funding Amount": funding.get("last_amount", ""),
        "Company Last Funding Date": funding.get("date", ""),
        "OEM Brand": existing_row.get("oem_brand", ""),
        "Location": loc_p.get("default", ""),
        "City": loc_p.get("city", "") or existing_row.get("city", ""),
        "State": loc_p.get("state", "") or existing_row.get("state", ""),
        "Country": loc_p.get("country", ""),
        "Company Location": loc_c.get("raw_address", "") or cf_loc.get("raw_address", ""),
        "Company City": loc_c.get("city", "") or cf_loc.get("city", ""),
        "Company State": loc_c.get("state", "") or cf_loc.get("state", ""),
        "Company Country": loc_c.get("country", "") or cf_loc.get("country", ""),
    }


def row_from_existing_only(existing_row):
    """Fallback when no raw record can be matched — populate what we already have."""
    return {
        "First Name": "", "Last Name": "",
        "Full Name": existing_row.get("contact_name", ""),
        "Email": existing_row.get("email", ""),
        "LinkedIn Profile": existing_row.get("linkedin", ""),
        "Job Title": existing_row.get("title", ""),
        "Company Name": existing_row.get("dealer_name", ""),
        "Website": existing_row.get("website", ""),
        "Domain": existing_row.get("website", ""),
        "Company LinkedIn": "", "Company Size": "", "No. of Employees": "",
        "Industry": "", "Company Description": "", "Company Primary Phone": "",
        "Company Founding Year": "", "Company Annual Revenue": "",
        "Company Total Funding": "", "Company Last Funding Type": "",
        "Company Last Funding Amount": "", "Company Last Funding Date": "",
        "OEM Brand": existing_row.get("oem_brand", ""),
        "Location": "", "City": existing_row.get("city", ""),
        "State": existing_row.get("state", ""), "Country": "",
        "Company Location": "", "Company City": "", "Company State": "",
        "Company Country": "",
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw-dir", default=None)
    ap.add_argument("--suffix", default="_clay", help="Output filename suffix before .csv")
    ap.add_argument("files", nargs="*", default=[
        "garrison_final.csv", "justin_final.csv", "mike_final.csv",
        "garrison_no_email.csv", "justin_no_email.csv", "mike_no_email.csv",
    ])
    args = ap.parse_args()

    print("Building lookup indexes from raw AI-Ark data...")
    by_linkedin, by_name_company = build_person_index(args.raw_dir)
    company_fallback = build_company_index(args.raw_dir)
    print(f"  {len(by_linkedin)} unique people by LinkedIn, {len(company_fallback)} companies")

    for fname in args.files:
        if not os.path.exists(fname):
            print(f"(skip {fname}: not found)")
            continue
        with open(fname, newline="", encoding="utf-8") as f:
            rows = list(csv.DictReader(f))

        out_rows = []
        matched = 0
        for r in rows:
            li = (r.get("linkedin") or "").strip().lower()
            name = (r.get("contact_name") or "").strip().lower()
            cname = (r.get("dealer_name") or "").strip().lower()
            item = by_linkedin.get(li) or by_name_company.get((name, cname))
            if item:
                out_rows.append(row_from_item(item, company_fallback, r))
                matched += 1
            else:
                out_rows.append(row_from_existing_only(r))

        out_path = fname.replace(".csv", f"{args.suffix}.csv")
        with open(out_path, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=HEADER)
            w.writeheader()
            w.writerows(out_rows)
        print(f"{fname} -> {out_path}: {len(out_rows)} rows ({matched} matched to raw data, "
              f"{len(out_rows)-matched} fallback-only)")


if __name__ == "__main__":
    main()
