# SPERA EDGE

Independent NIFTY 500 research and trade-planning application. The original SPERA Wisdom project is not modified. No brokerage orders are implemented.

## Four tabs

- Market Pulse: dated breadth, advances/declines, expansion/deterioration, conservative participation heuristics and official current-industry research.
- Leadership Scanner: frozen Momentum V1, price-only Stage 2 template, universe-relative strength, institutional 12-1/path diagnostics and explicit evidence gates. PASS, REVIEW and FAIL remain separate.
- Trade Desk: VCP research, prior-session pivot and volume confirmation, protective-stop reference, risk/exposure-capped sizing, selected watchlists and CSV exports. Technical confirmation is not a certified SEPA signal.
- Portfolio & Journal: authenticated, owner-scoped, append-only D1 ledger for long entries, partial exits, stops, fees, review notes, realized/unrealized P&L, exposure and risk.

## Data and limitations

GitHub Actions refreshes the existing independent Upstox OHLCV snapshot and EDGE D1 research storage. Current NSE industry membership is separately dated and checksum-verified. Historical SPERA Wisdom sector rankings remain archived evidence. Benchmark history is looked up by identity in the provider master; missing benchmark data stays unavailable. Corporate-action adjustment and independently verified earnings/sales evidence remain required before certification. No automatic PASS upgrades are performed. Historical breadth uses the available current universe and has survivorship limitations. VCP range rules and market-condition thresholds are explicitly labeled research heuristics.

## Private journal configuration

The private tab is locked before database reads unless Streamlit OIDC and an explicit EDGE_JOURNAL_ALLOWED_EMAILS list are configured. Follow Streamlit official OIDC authentication documentation. Configure [auth] with redirect_uri, cookie_secret, client_id, client_secret and server_metadata_url. The identity provider must supply verified email, email_verified=true, issuer (iss) and subject (sub). Streamlit sharing access alone is not journal authentication.

Set EDGE_CF_ACCOUNT_ID, EDGE_D1_DATABASE_ID and EDGE_CF_API_TOKEN in Streamlit secrets for the independent EDGE database only. GitHub repository secrets do not automatically become Streamlit secrets. The ledger uses parameterized owner-scoped queries, atomic revision checks and idempotent submission IDs. Legacy unscoped edge_journal records are not exposed or automatically migrated. Never commit credentials.

Accounting uses average cost including transaction fees. Stops do not guarantee fills. Missing/stale marks disable new-entry sizing; breached recorded stops block new entries. Positions are long-only. Manually entered account equity must be verified independently.

## Verification

Run python -m unittest discover -s tests -v and python -m compileall -q app.py edge_workspace.py edge_evidence.py edge_core tests tools. The frozen V1 source hash and ranking regressions are checked.

Run Actions > Verify EDGE persistence and release to verify independent D1 write/read, owner isolation and published research counts. This retains an explicitly labeled synthetic technical NOTE under a unique probe owner, never as an actual trade. Authenticated production-user journal verification additionally requires the private configuration above.

Production deploys main/app.py through Streamlit Community Cloud. Verify all four deployed tabs and downloads separately from CI.
