# SPERA EDGE — lean delivery roadmap

## Implemented in source
- Private repository, four-screen Streamlit research UI
- Frozen V1 scorer, institutional V2 and VCP scanner copied without formula changes
- Market breadth and Stage 2 price-only diagnostics
- Manual CSV import and candidate exports
- Read-only Upstox daily historical candle adapter
- Unit tests and GitHub Actions quality workflow

## Next release gates
1. GitHub Actions quality tests must pass; fix failures before deployment.
2. Obtain valid Upstox access token securely. API key and secret alone do not provide a live token; OAuth reauthorization may be required.
3. Resolve trusted official universe and instrument-key mapping; fetch aligned OHLCV, validate session dates and corporate actions.
4. Publish a coherent dated research snapshot with coverage and PASS/REVIEW/FAIL states. Do not claim live/certified output before this.
5. Wire snapshots into Streamlit; deploy separately from existing SPERA.
6. Add persistent journal and portfolio risk ledger, isolated storage, and backups.
7. End-to-end audit, operations documentation, then production release.

No automatic brokerage orders. No trading performance promises. Original SPERA repositories remain untouched.
