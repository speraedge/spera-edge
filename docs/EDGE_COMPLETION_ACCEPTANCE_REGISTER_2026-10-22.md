# SPERA EDGE — Evidence-Based Completion Register

Updated 2026-10-22. Scope: `speraedge/spera-edge`, development branch `milestone2-evidence-audit`. This register measures **acceptance**, not code volume or CI green status. Never use an overall percentage without an independently checked denominator.

## State definitions

- **IMPLEMENTED**: code exists; this is not proof of correct live behavior.
- **OFFLINE_TESTED**: automated tests have passed for the covered contract only.
- **LIVE_VERIFIED**: actual target infrastructure, authenticated flows or real data have been checked with recorded evidence.
- **ACCEPTED**: documented owner-approved release acceptance, including required provenance and fail-closed behavior.
- **BLOCKED**: external access, missing source or unverified evidence prevents acceptance.

## Acceptance matrix

| Workstream | Current evidenced state | Missing acceptance evidence |
| --- | --- | --- |
| Frozen Momentum V1 ranking | OFFLINE_TESTED | Independent representative real-market replay and no-regression acceptance |
| Market Pulse and sector participation | OFFLINE_TESTED | Dated live freshness, point-in-time membership and sector evidence |
| Daily OHLCV ingestion | IMPLEMENTED | Provider-to-published-snapshot freshness, completeness, retry and recovery checks |
| Corporate-action adjustments | BLOCKED | Verified split/bonus event coverage and adjusted-price reconciliation |
| Relative strength and SEPA gates | IMPLEMENTED | Independent benchmark, identity and complete technical evidence |
| VCP/pivot/volume research | OFFLINE_TESTED | Representative actual setups, negative cases and forward validation |
| Risk and position planning | OFFLINE_TESTED | End-to-end realistic fill, gaps, exposure and account-state verification |
| Private Portfolio & Journal | OFFLINE_TESTED | Owner OIDC live sign-in, D1 isolation and read/write acceptance |
| Financial filing acquisition | IMPLEMENTED | Permitted official acquisition, source provenance and figures for genuine issuers |
| Financial comparability/reconciliation | OFFLINE_TESTED | Real source-document reconciliation across period, basis, units and restatements |
| Financial evidence review | OFFLINE_TESTED | Owner-authenticated production review and append-only ledger acceptance |
| CSV/Excel/PDF section exports | OFFLINE_TESTED | Actual downloads, wide datasets, special characters and mobile acceptance |
| Historical point-in-time validation | BLOCKED | Survivorship-free historical membership, adjustment and out-of-sample evidence |
| Scheduled publication and persistence | IMPLEMENTED | Latest live schedule and independent EDGE D1 publication/readback checks |
| Security and production release | BLOCKED | OIDC, secrets, permissions, failure recovery, live smoke and owner release approval |

These states are conservative; older evidence may exist but must be linked and checked before promotion. An existing successful synthetic D1 smoke test does not establish current production acceptance. None of these rows is marked ACCEPTED.

## Mandatory execution order

### Gate A — integration and regression baseline
1. Inventory existing code and test coverage against the frozen contracts.
2. Verify one current end-to-end dry run from dated snapshot to leadership, setup, risk and export.
3. Confirm unchanged frozen ranking fixtures and fail-closed behavior on missing/stale evidence.
4. Record workflow run ID, commit SHA, sample date, inputs and actual outputs.

### Gate B — authoritative market-data integrity
1. Audit Upstox instrument identity, completed sessions, duplicates, missing candles and freshness.
2. Check independent EDGE D1 published snapshot readback and last-known-good behavior.
3. Reconcile official membership and benchmark provenance; do not substitute current constituents for historical ones.
4. Track corporate-action coverage separately; unknown remains REVIEW.

### Gate C — genuine financial evidence
1. Connect shortlist to exact official filing register and acquisition outcomes.
2. Preserve symbol/ISIN, period, reporting basis, publication date, original URL, hash and acquisition status.
3. Independently reconcile revenue/PAT, units, like-for-like periods and restatements.
4. Route missing/conflicting evidence to quarantined operator review; never auto-certify.

### Gate D — real operator and release acceptance
1. Verify authenticated owner-only portfolio, financial review and D1 isolation in the actual app.
2. Exercise real CSV, XLSX and PDF downloads from every relevant section, including mobile.
3. Test scheduler failure, recovery, source 403/429, stale snapshots and rollback.
4. Require clean CI plus live evidence, security review and explicit owner approval before merging or deploying.

## Engineering safeguards

- Make coherent changes on the development branch only; never silently merge into `main`.
- Run syntax compilation, focused tests, full unit tests and changed-feature acceptance before claiming success.
- Never alter frozen Momentum V1 scoring, ranking, or its historical assumptions without explicit approval.
- Never mark financial evidence, corporate actions, SEPA decisions or trading signals certified on the basis of synthetic fixtures.
- Record each failure's root cause and add a regression test; do not rely on trial-and-error commits.
- Every handoff must state **implemented**, **tested**, **live verified**, **blocked** and **not attempted** separately.
- Stop and request credentials or user action only when a true external authorization boundary blocks progress. Never ask users to share secrets in chat.

## Immediate next delivery

Gate A: source-and-test coverage inventory and one dated, repeatable end-to-end research acceptance harness. Gate B and Gate C should not be represented as complete until their real evidence is captured.
