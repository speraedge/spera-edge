# SPERA EDGE

Private, independent momentum research and trade-planning application built with Streamlit.

## Screens
- Market Pulse: market regime and breadth (requires verified market history)
- Leadership Scanner: momentum candidates and trend-template screening
- Trade Desk: VCP research candidates requiring manual chart validation
- Portfolio & Journal: manual trade planning and journal entries

## Status
Initial application scaffold. No live feed, brokerage execution, certified signals, persistence, or scheduled jobs are enabled. The source SPERA project is not modified.

## Local start
```bash
pip install -r requirements.txt
streamlit run app.py
```

## Credentials
The same Upstox developer application may be reused. Never commit keys, secrets, or tokens. Configure `UPSTOX_API_KEY`, `UPSTOX_API_SECRET`, and a valid `UPSTOX_ACCESS_TOKEN` only in a secure secret store when the API adapter is activated. Tokens expire; unattended renewal is not assumed.

## Isolation
Use separate storage and deployment resources from the existing SPERA project. Any inherited ranking module must be reviewed against its frozen contract before import.

## Upstox verification

GitHub Actions reads either `UPSTOX_ACCESS_TOKEN` or `UPSTOX_ANALYTIC_TOKEN` (an actual OAuth access token, not API key/secret). To check live access, open Actions > Upstox read-only smoke > Run workflow. The workflow requests RELIANCE historical candles and never prints credentials. Tokens can expire and need reauthorization. CI and deployment are separate; no Streamlit deployment has been performed.

## Streamlit Community Cloud release

Deploy the private GitHub repository `speraedge/spera-edge`, branch `main`, main file `app.py`. Add `UPSTOX_ACCESS_TOKEN` to **Streamlit app secrets**; GitHub Actions secrets are not automatically available to Streamlit. The token must be a current OAuth access token. The app's sidebar can fetch one instrument's historical daily candles for a read-only connection check. It does not populate a certified universe-wide live leaderboard automatically.

Production limitations: no persistent journal database, no validated universe membership or corporate-action adjustment, no automated weekly live refresh, and no broker orders. Session journal must be exported before closing the app. Review GitHub Actions quality checks and live Streamlit logs before relying on results.
