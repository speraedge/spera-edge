# SPERA EDGE — Maintenance

## Daily NIFTY 500 price snapshot
GitHub Actions workflow: `.github/workflows/edge-snapshot.yml`.
Runs Monday–Friday at **22:30 IST (17:00 UTC)** using cron `0 17 * * 1-5`.
The existing **single 30-minute stale-provider retry** remains enabled. The job validates freshness before publishing; GitHub-hosted scheduled runs can start later than their nominal time. A successful job does not certify corporate actions or trade readiness.

## Quarterly fundamentals: manual, local, zero-cost
**Do not automate the fundamentals fetch on GitHub Actions or another cloud runner.** NSE/BSE endpoints have blocked cloud IP requests in this workflow. The supported process uses the `dalal` Python library **on your local laptop**, approximately **once every three months, after quarterly earnings releases**. This is an operator-initiated refresh, not a nightly task. Because companies report on different dates, verify each `Quarter_End` and rerun when reporting coverage has improved; do not label stale quarters as current.

From the repository root on the laptop (with Python and the project's dependencies, including `dalal==0.2.1`, installed):

1. Ensure `data/latest/current_membership.csv` and `data/latest/bse_mapping.csv` are present and correspond to the intended universe. If BSE mapping needs refreshing, download the official BSE CM UDiFF Bhavcopy CSV in a browser and run `python tools/build_bse_bhavcopy_mapping.py --manual "data/manual/<BSE_BHAVCOPY_FILENAME>.CSV"` after placing it in `data/manual/`. This is optional when a valid mapping is already present.
2. Run exactly: `python tools/fetch_fundamentals_local.py`.
3. Review the console counts and `data/latest/fundamentals_auto.csv`. Check `AUTO` versus `AUTO_FAILED` rows, source, quarter end, and a sample of published company filings. Do not invent missing data.
4. **Manually upload only** `data/latest/fundamentals_auto.csv` to the same path in the GitHub repository's `main` branch, replacing the prior file. Verify the commit and live Streamlit Trade Desk → Fundamentals table. Do not upload private D1 records, secrets, or raw manual notes.

The public CSV includes quarterly **Revenue, PAT, EPS, and Quarter_End** where verified. **P/E and Market_Cap are intentionally blank**: the current `dalal` response does not establish the necessary market price / shares-outstanding inputs to calculate them reliably. Minervini-style fundamental screening emphasizes **EPS and revenue growth** rather than requiring P/E; however, a single quarterly snapshot does **not** establish growth without comparable prior periods. Do not claim growth metrics are computed from this CSV alone.

Private manual financial values belong exclusively to the owner-scoped D1 overlay, merged in memory at request time; never copy them into the public CSV.

## Known limitations
- BSE mapping and financial acquisition may not cover every NIFTY 500 member. Preserve missing/error statuses; investigate failures individually.
- Quarterly values may differ by consolidated/standalone basis; check reporting basis before cross-company comparisons.
- The research dashboard may remain flagged `REVIEW_UNVERIFIED_CORPORATE_ACTIONS`; this is not a certified execution signal.
- Daily snapshot and quarterly fundamentals are **separate** processes. The nightly job intentionally does not stage or overwrite `fundamentals_auto.csv`.
