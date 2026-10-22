# SPERA EDGE — Release Verification and Remaining Gates

Status: **RESEARCH APPLICATION DEPLOYED; NOT SEPA-CERTIFIED**.

## Scope and separation
- Repository: `speraedge/spera-edge`. The legacy SPERA Wisdom repository remains untouched.
- Research-only Streamlit application. No brokerage execution.
- Four tabs: Market Pulse, Leadership Scanner, Trade Desk, Portfolio & Journal.
- Frozen Momentum V1 qualification must not be altered or silently promoted to certified PASS.

## Confirmed in repository
- `app.py` integrates `edge_workspace` market, entry, industry and private portfolio functions.
- `edge_evidence.py` retrieves dated NSE membership and identified NIFTY 500 benchmark history.
- `.github/workflows/edge-snapshot.yml` includes evidence publication.
- `.github/workflows/verify-edge.yml` runs tests, compilation, snapshot validation and an isolated D1 write/read and owner-isolation probe.
- The 2026-10-21 snapshot metadata reports 500 mapped/retrieved histories, quality `REVIEW_UNVERIFIED_CORPORATE_ACTIONS`, `certified: false`, and zero research PASS.

## Codex production checks (reported, not independently reproduced here)
- Release workflow passed with a D1 write/read, owner isolation and 501 stored research rows.
- Refreshed pipeline passed and published membership and benchmark history.
- Market Pulse industry research rendered and breadth CSV downloaded.
- Trade Desk 500 exported entry rows matched independent calculations.
- Leadership qualification export contained 501 rows, 478 with benchmark RS; none certified.
- Risk calculator produced zero quantity at the portfolio risk ceiling.
- Local tests and four-tab rendering passed.

## Deliberately deferred: private journal login
The user chose to configure privacy later. **Do not remove or bypass authentication.** The first three research tabs may remain accessible. The Portfolio & Journal database must remain locked until Streamlit OIDC, `EDGE_JOURNAL_ALLOWED_EMAILS` and EDGE D1 secrets are configured. Never expose D1 credentials, private trades or journal records in public exports.

## Remaining acceptance gates
1. Confirm the latest quality and snapshot workflow results on GitHub Actions after the final commit, including any scheduled refresh failures.
2. Confirm production deploy SHA matches the intended GitHub main revision and validate all four tabs and downloadable exports.
3. Confirm D1 research counts, date and owner-isolation probe remain correct; do not mistake a synthetic probe for a real journal trade.
4. Preserve explicit unavailable/review flags for unverified corporate actions, financial earnings/sales and other SEPA certification evidence.
5. When requested later, configure and verify Google OIDC for `sperawisdom@gmail.com`, then test allowed and rejected accounts before enabling private journal reads.

## Release decision
Research and risk-planning functions may be used as **uncertified decision support** with dated data and warnings. This report does not certify live trading signals, corporate-action adjustments, fundamentals, or private journal login.
