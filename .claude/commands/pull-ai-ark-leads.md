---
description: Pull net-new ICP contacts via AI-Ark (real-dealer verified, description-audited), export to Clay format, merge, save to Desktop.
---

Run the AI-Ark contact-pull pipeline built for the Spiffy KALI campaign, working in `dealerrater-scraper/ai_ark_pipeline/`. Arguments (if given): `$ARGUMENTS`.

## 1. Determine scope

- No arguments, or an argument like "garrison" / "justin" / "mike" / "all reps" → use the default campaign: all 3 reps from `config.py`'s `REP_STATES`, full `OEM_BRANDS` list, full ICP title list. Run one pull per rep.
- A custom scope (different states, brands, or titles) → this is one ad-hoc pull. Pick a short `--label` for it (e.g. `texas-luxury`).

For each pull, get the exact query parameters first instead of re-deriving them by hand:
```
cd ai_ark_pipeline
python3 query_builder.py --rep garrison        # predefined rep
# or
python3 query_builder.py --states "Texas,Oklahoma" --brands "Ford,Toyota" --titles "service manager,general manager" --label texas-ford-toyota
```
This prints the exact `mcp__ai-ark__email_finder` params (including the uppercase `excludeCompanyType` enum quirk that isn't documented correctly in the tool schema).

## 2. Run the query and paginate

Call `mcp__ai-ark__email_finder` with those params (ToolSearch for it first if not loaded). It returns a `trackId` in `PENDING` state.

Poll `mcp__ai-ark__email_finder_results` (trackId, page=0, size=100) — it'll error `409 track id in progress` while processing. Wait via a backgrounded `sleep` (never a bare blocking sleep) and retry; large territories (10,000-cap queries) can take 5-10+ minutes.

Once page 0 succeeds, check `totalPages` in the response. For each page:
```
python3 process_results.py <saved_json_path> <label> <label>_final.csv
```
The MCP tool auto-saves large results to a file and gives you that path — pass it straight through, don't try to inline the JSON.

Fire 8-10 `email_finder_results` calls in parallel per turn to get through many pages fast. **For more than ~20 remaining pages, delegate to a background Agent** rather than doing it all inline — see the pattern used in this project's history: give the agent the trackId, the already-done page range, the exact `process_results.py` command, and tell it to batch-fetch + process the rest, reporting back the final row count.

## 3. Clean up known collision brands

Some brand names collide heavily with unrelated companies — this was discovered the hard way:
- **Drop entirely** (near-100% false positive rate, or not sold via a franchise/dealer model in the US): Smart, Tesla, Scion, Saab, Suzuki — already hardcoded as `filters.DROP_BRANDS`.
- **Ram**: real dealers almost always sell alongside Dodge/Chrysler/Jeep. `filters.py` already requires a companion word (dodge/chrysler/jeep/cdjr/truck/auto/motors/dealer) in the company name — don't loosen this.
- **Lincoln, Mini**: extremely generic words (Lincoln Electric, WillScot Mobile Mini, Mini Melts...). `filters.py` already requires `industry` to be motor-vehicle/retail/automotive for these two — if a future brand shows the same pattern (many hits, obviously-wrong sample), add it to `STRICT_INDUSTRY_BRANDS` rather than trusting name-match alone.

Run the purge pass after collecting all pages for a pull:
```
python3 final_purge.py <label>_final.csv
```

## 4. Description-level audit (don't skip this — the user explicitly cares about it)

Company `industry` tags are unreliable (confirmed repeatedly — warranty vendors, R&D labs, health insurers, and university clubs all get tagged "motor vehicle manufacturing"). Verify against actual company description text:
```
python3 audit_descriptions.py <label>_final.csv
```
This prints a breakdown (CONFIRMED_NEW_CAR_DEALER / AMBIGUOUS / NO_DATA / FLAGGED_NON_DEALER) and — combined with `final_purge.py` — removes flagged non-dealers.

If you spot a new contamination pattern during a future run (a brand/company-type that's slipping through), **add the pattern to `NON_DEALER_RE` in `audit_descriptions.py`**, re-run, and sanity-check with a random sample before trusting the count — this list has needed several rounds of tightening historically; don't assume a first pass is clean. Watch in particular for: generic-word brand collisions, corporate/manufacturer parents vs. local retail franchises, and non-dealer businesses that happen to use the same word (law firms, hospitals, staffing agencies, etc. — see the full pattern list already in the file for examples of what's been caught before).

## 5. Export contacts with no verified email too (for Clay)

Don't silently drop people who passed every filter but lack a verified email — the user wants those separately for Clay enrichment:
```
python3 export_no_email.py --with-email-files <label>_final.csv
```
(Defaults to scanning every raw file for the current session's auto-detected directory; pass `--raw-dir` explicitly only if auto-detection picks the wrong session.)

## 6. Reformat to the Clay column schema

```
python3 export_clay_format.py <label>_final.csv <label>_no_email.csv
```
Produces `<label>_final_clay.csv` and `<label>_no_email_clay.csv` with columns: First Name, Last Name, Full Name, Email, LinkedIn Profile, Job Title, Company Name, Website, Domain, Company LinkedIn, Company Size, No. of Employees, Industry, Company Description, Company Primary Phone, Company Founding Year, Company Annual Revenue, Company Total Funding, Company Last Funding Type, Company Last Funding Amount, Company Last Funding Date, OEM Brand, Location, City, State, Country, Company Location, Company City, Company State, Company Country.

## 7. Merge with-email + no-email into one file per label

```
python3 merge_with_no_email.py <label>_final_clay.csv <label>_no_email_clay.csv <label>_merged.csv
```

## 8. Save to Desktop and report

Copy `<label>_merged.csv` to `~/Desktop/Spiffy KALI - ICP Contacts/<Label>_ICP_Contacts.csv` for each pull (overwrite is fine — that's the expected refresh behavior). Verify row counts with a CSV-aware count, not `wc -l` (Company Description fields contain embedded newlines that break naive line counting):
```
python3 -c "import csv; print(sum(1 for _ in csv.reader(open('FILE'))) - 1)"
```

Report back: final row count per label, split into with-email vs. no-email, and flag anything that looks off (e.g. a brand suddenly dominating the results the way Smart/Ram did historically — that's usually a new collision pattern, not real volume).

## Also remember

- `used_domains.txt` is the "already contacted for Spiffy" exclude list — keep it updated with every new domain that goes into a final export, or future pulls will re-surface the same dealers. After a successful run, append the new pull's domains to it.
- Never contact Hyundai or Genesis — they're not in `config.OEM_BRANDS` and must stay out.
