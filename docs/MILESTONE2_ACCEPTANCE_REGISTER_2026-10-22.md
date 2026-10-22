# Milestone 2 acceptance register — 22 October 2026

Scope: `milestone2-evidence-audit` development branch. This document is a gate register, not a release approval.

| Gate | State | Evidence / remaining requirement |
| --- | --- | --- |
| Shortlist → official filing register → PDF acquisition → review export | CODE COMPLETE / OFFLINE TESTED | Integration tests in `tests/test_shortlist_financial_audit.py`; successful PDF, missing source, HTTP 403, mixed companies |
| Official source URL and SHA-256 preservation | CODE COMPLETE / OFFLINE TESTED | `tools/shortlist_financial_audit.py` passes source and digest to `validate_acquisition_import` |
| Owner-scoped, append-only reconciliation D1 ledger | CODE COMPLETE / OFFLINE TESTED | SQLite replay, isolation, deletion rejection; live expanded smoke still outstanding |
| Genuine official-source multi-company reconciliation | BLOCKED / NOT CERTIFIED | Requires independently verified issuer, reporting basis, publication date, values, restatements and source documents |
| Live EDGE D1 end-to-end acceptance | PENDING | Run `python tools/verify_edge_d1.py --live` with EDGE-only credentials in a secure environment; inspect results |
| Authenticated production operator UI | PENDING | Verify login, owner isolation, file upload, error states and audit history in deployed environment |
| Price/corporate-action/historical point-in-time certification | PENDING | Independent adjustments, membership and benchmark history audits |
| Release | NOT APPROVED | Require all mandatory acceptance gates, full CI and explicit production approval |

A passing GitHub Actions quality workflow verifies automated tests only. It does not establish genuine filing authenticity, live infrastructure acceptance or certified trading signals.

## Final engineering handoff
1. Review full CI for the latest development commit.
2. Perform permitted multi-company real filing audit, retain original documents and manifest hashes.
3. Execute live EDGE D1 smoke with secure credentials and record immutable-event, owner-isolation and replay results.
4. Run authenticated deployed UI acceptance; no production merge before explicit approval.
5. Complete independent corporate-action and point-in-time audits, document unresolved evidence as REVIEW_REQUIRED.
6. Publish an evidence-backed release decision; keep uncertified output quarantined.
