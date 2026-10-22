# SPERA EDGE — Working Blueprint V2 (2026-10-22)

Status: APPROVED OPERATING DESIGN; implementation remains staged and uncertified. This blueprint does not supersede frozen Momentum V1 rules or authorize trading signals.

## Boundaries
- Repository: speraedge/spera-edge only. Original SPERA Wisdom, Railway and legacy D1 are untouched.
- Production remains on main; Milestone 2 work stays on development branch until independently verified.
- Four existing product areas remain: Market Pulse, Leadership Scanner, Trade Desk, Portfolio & Journal.
- No brokerage execution. Never promote research candidate to certified PASS without evidence.

## Daily price lane
- Upstox OHLCV, volume, instrument identity, benchmark history; backfill then incremental trading-day updates.
- Validate session date, expected symbol/ISIN, duplicates, missing candles, provider errors, staleness, and price discontinuities.
- Corporate-action adjustment is a separate gate: Upstox candle availability alone is NOT historical adjustment certification.
- Retain last known good snapshot with explicit as-of timestamp and STALE status if refresh fails; never label it current.

## Quarterly/annual financial lane
- Check new reporting events periodically; refresh financials only when results become available, corrected, or restated.
- Use permitted official NSE/BSE documents, company investor-relations reports, and Screener.in as a human research/cross-check reference where permitted. Do not scrape restricted sites or evade 403/429.
- Minimum statement record: symbol, ISIN, period_end, period_type Q/FY, basis CONSOLIDATED/STANDALONE, revenue, PAT, published_on, source_url. Store source hash and acquisition/verification metadata when available.
- Compare like-for-like periods and bases, preserve prior versions and actual public availability dates. Compute growth; do not accept user-entered growth percentages as primary facts.
- Additional metrics (ROCE, D/E, EPS, margin, etc.) require separately approved rules; do not silently change qualification criteria.

## Corporate-action lane
- Collect split/bonus terms, event and ex-dates, instrument identity, source and original document evidence; reconcile adjusted price history.
- Dividend evidence must not be mistaken for a split/bonus price-adjustment factor.
- Missing event coverage remains REVIEW, not evidence that no events occurred.

## Evidence fallback and operator queue
- For technically shortlisted stocks only, compare required fields against verified current-period records.
- Create deterministic review requests for missing, stale, conflicting or unverified evidence, with specific missing field names, period, basis and source expectations.
- Never require operator to re-enter already verified fields. Manual entries are quarantined until source/identity/period/unit checks and original-document reconciliation.
- Manual input must retain submitter, timestamp, source URL, source document hash if available, and immutable correction history.
- Manual entry alone is never independent verification, and never overrides frozen technical rules.
- Support no-data, inaccessible-source, partial-evidence and rejected-evidence states.

## Decision states
- TECHNICALLY_QUALIFIED_EVIDENCE_PENDING: price-based candidate with unresolved fundamentals/actions.
- MANUAL_REVIEW_PENDING: human evidence submitted but not certified.
- VERIFIED_RESEARCH_ELIGIBLE: all required independent gates verified, subject to explicit approved final rules.
- REVIEW_REQUIRED: conflict, stale, missing or unverifiable source.
- FAIL: actual frozen-rule failure only; never infer from absence of data.

## Frequency and resilience
- Prices: every trading day (provider permitting); weekly research publication as configured.
- Fundamentals: quarterly/annual event-driven; checks can run more often without treating unchanged data as stale by default.
- Corporate actions: event-driven, plus historical coverage audits.
- Cache immutable source artifacts and verified records in EDGE-controlled storage, not only a third-party website.
- Source HTTP 403/429: stop bounded retries, mark source blocked, use permitted alternatives or manual queue. Never bypass.
- Alert only on actionable gaps; show latest successful as-of and next expected source event.

## Build sequence and acceptance gates
1. Frozen contract audit and data inventory: map each final output to required fields and freshness gates.
2. Deterministic, unit-tested shortlist evidence queue (no network, no certification), plus export/import contract.
3. Real Upstox incremental freshness validation and persistent EDGE D1 snapshots; verify actual schedule/run evidence.
4. Permitted source acquisition, original-file hashing and structured reconciliation on a multi-company pilot.
5. Secure authenticated operator review interface and append-only D1 evidence ledger, no arbitrary data edits.
6. Corporate-action and point-in-time history certification, expanded sample, and fail-closed regression tests.
7. Release gate: CI + live persistence + source provenance + security + frozen V1 invariance + production UI.

## Not yet complete
Automatic multi-source financial retrieval, quarterly-result detection, production manual-review queue, complete corporate-action adjustments, independent historical certification, and final certified SEPA outputs. Do not describe these as shipped.


## Delivery status and work register — updated 22 October 2026

This section is a dated implementation ledger, not an amendment to the frozen rules above. No percentage is asserted for independent certification.

| Workstream | Implemented | Verified boundary | Open acceptance gate |
| --- | --- | --- | --- |
| Market Pulse | Streamlit market breadth, participation and industries | Historical code/tests; current production release not re-certified here | Daily freshness, point-in-time breadth and published UI |
| Leadership Scanner | Frozen Momentum V1 ranking, relative strength and official NIFTY 500 identity | Published identity evidence and regression coverage | Independent price adjustment, RS and historical membership audit |
| Trade Desk | VCP/pivot/volume research and risk planning | Offline research tests | Setup correctness, forward validation and certified signal policy |
| Portfolio & Journal | Accounting and risk backend | Backend tests | Production owner authentication and end-to-end UI verification; authentication deliberately deferred |
| Financial Evidence Review | Shortlist, deterministic queue, manual intake, owner-scoped append-only D1 ledger | Live synthetic D1 persistence, quarantine, owner isolation and idempotency passed in Actions 39734370759 | Authenticated production UI and genuine financial source reconciliation |
| Official filing acquisition | Explicit NSE/BSE HTTPS PDF downloader, SHA-256 manifest, no redirects and 25 MB bound | Offline acquisition tests | Permitted filing discovery, reporting metadata completeness, issuer authenticity and extracted figures |
| Acquisition register bridge | Exact symbol/ISIN/period/type/basis matching; ambiguity and absent source remain review | Five offline tests passed in failed aggregate run 39751486743 | Connect bridge to acquisition, reconciliation, queue, ledger and UI |
| Financial comparability and reconciliation | Separate arithmetic, statement/document and transcription review modules | Offline tests; output explicitly uncertified | Cross-module orchestration, actual source verification and correction/restatement audit |
| Corporate actions | Evidence import/research scaffolding | Not independently certified | Split/bonus adjustment and point-in-time coverage |
| GitHub operations | Quality workflow and historical successful live D1 smoke test | Run 39751486743 failed 2/107 due to CSV fixture column mismatch; correction committed a11f40a | Confirm fresh successful CI on corrected branch, then integration acceptance |
| Production release | Existing Streamlit application on main | Latest development features are NOT confirmed deployed | Separate release approval and live smoke test |

### Next cohesive milestone: official financial acquisition and reconciliation

1. Preserve frozen V1 and separate EDGE database boundaries; do not merge development changes prematurely.
2. Connect shortlist to exact official filing register and acquisition results, retaining symbol, ISIN, Q/FY, reporting basis, publication date, source URL, SHA-256, HTTP outcome and immutable provenance.
3. Implement only permitted source discovery where authoritative endpoints allow it; handle 403/429 with bounded retry and explicit blocked-source review. Do not infer missing filings or invent data.
4. Reconcile statement identity, units, periods, basis, original source, document digest, revenue/PAT and restatements; fail closed on mismatches.
5. Route unresolved evidence into deterministic operator review. Manual entries remain quarantined and never independently certify themselves.
6. Exercise synthetic success, absent source, HTTP 403/429, duplicates, wrong ISIN, ambiguous filings, inconsistent basis, partial fields, replay and owner isolation.
7. Require clean full CI, documented live-infrastructure evidence, and explicit release approval before production deployment. Distinguish offline PASS, live persistence PASS, verified financial data and certified trading signals.

### Last-known source-of-truth references

- Repository: `speraedge/spera-edge`; development branch: `milestone2-evidence-audit`; draft PR #1.
- Live D1 smoke: Actions run `39734370759`, synthetic quarantined event retained append-only.
- Acquisition bridge commits: `a406e0c`, `7c8f533`.
- Quality failure: Actions run `39751486743`, 105 tests passed, two fixture errors.
- Fixture repair commit: `a11f40a` (CI outcome must be checked separately).
- This blueprint remains an operating specification; a code commit does not imply successful deployment or certified data.
