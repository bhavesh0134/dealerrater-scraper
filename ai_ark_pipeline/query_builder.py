#!/usr/bin/env python3
"""
Print ready-to-use parameters for the mcp__ai-ark__email_finder tool call —
so Claude doesn't have to re-derive the query shape (correct enum casing,
which fields go where, default brand/title lists) each time.

Usage:
    python3 query_builder.py --rep garrison
    python3 query_builder.py --states "Texas,Oklahoma" --brands "Ford,Toyota" \
        --titles "service manager,general manager" --label texas-ford-toyota

Defaults to the full campaign brand list and ICP title list from config.py
if --brands/--titles aren't passed. --rep pulls states from config.REP_STATES;
--states overrides with a custom comma-separated list of full state names
(must match the AI-Ark location enum, e.g. "New York" not "NY").
"""
import argparse
import json

from config import REP_STATES, OEM_BRANDS, API_TITLE_QUERY


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rep", choices=list(REP_STATES.keys()), default=None,
                     help="Use a predefined rep's territory from config.py")
    ap.add_argument("--states", default=None,
                     help="Comma-separated full state names (overrides --rep)")
    ap.add_argument("--brands", default=None,
                     help="Comma-separated OEM brand names (default: full campaign list minus DNC)")
    ap.add_argument("--titles", default=None,
                     help="Comma-separated job titles (default: full ICP title list)")
    ap.add_argument("--label", default=None,
                     help="Label to use for output files (default: rep name or 'custom')")
    ap.add_argument("--size", type=int, default=10000, help="Max results to request (API cap 10000)")
    args = ap.parse_args()

    if args.states:
        states = [s.strip() for s in args.states.split(",") if s.strip()]
    elif args.rep:
        states = REP_STATES[args.rep]
    else:
        raise SystemExit("Pass either --rep or --states")

    brands = [b.strip() for b in args.brands.split(",")] if args.brands else OEM_BRANDS
    titles = args.titles if args.titles else API_TITLE_QUERY
    label = args.label or args.rep or "custom"

    params = {
        "companyKeyword": ",".join(brands),
        "companyKeywordSources": "NAME",
        "companyKeywordMode": "WORD",
        "companyLocation": ",".join(states),
        "excludeCompanyType": "PUBLIC_COMPANY,NON_PROFIT,GOVERNMENT_AGENCY,EDUCATIONAL",
        "maxEmployees": 500,
        "title": titles,
        "size": args.size,
    }

    print(f"# label: {label}")
    print("# Call mcp__ai-ark__email_finder with these params:")
    print(json.dumps(params, indent=2))
    print()
    print("# Reminders:")
    print("#  - excludeCompanyType values MUST be uppercase (documented lowercase is wrong)")
    print("#  - After getting a trackId, poll mcp__ai-ark__email_finder_results (page=0, size=100) until it stops erroring '409 track id in progress'")
    print("#  - Paginate through all totalPages (fire ~8-10 email_finder_results calls in parallel per turn)")
    print("#  - Each page: python3 process_results.py <saved_json_path> " + label + f" {label}_final.csv")
    print("#  - For pages > ~20, delegate remaining pagination to background Agent calls (see project notes)")


if __name__ == "__main__":
    main()
