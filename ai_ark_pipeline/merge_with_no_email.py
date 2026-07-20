#!/usr/bin/env python3
"""Merge a with-email export and a no-email export into one CSV (same schema)."""
import argparse
import csv


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("with_email_csv")
    ap.add_argument("no_email_csv")
    ap.add_argument("out_csv")
    args = ap.parse_args()

    with open(args.with_email_csv, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        header = reader.fieldnames
        rows = list(reader)
    with open(args.no_email_csv, newline="", encoding="utf-8") as f:
        rows += list(csv.DictReader(f))

    with open(args.out_csv, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=header)
        w.writeheader()
        w.writerows(rows)

    email_col = "Email" if "Email" in header else "email"
    with_email = sum(1 for r in rows if r.get(email_col))
    print(f"{args.out_csv}: {len(rows)} total rows "
          f"({with_email} with email, {len(rows) - with_email} without)")


if __name__ == "__main__":
    main()
