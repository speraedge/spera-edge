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
