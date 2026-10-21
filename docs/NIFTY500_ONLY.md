# SPERA EDGE — single-universe contract

**Only active universe: NIFTY_500.** Total Market is out of scope for this release.

Source contract: the original `SperaWisdom/spera-wealth-dashboard` frozen NIFTY 500 universe and momentum V1 rules. Copied modules live in `edge_core/momentum_universe.py` and `edge_core/momentum_v1.py`. The source repository is read-only to this project.

## Required automated flow
1. Retrieve official NIFTY 500 constituent CSV; fail closed on invalid count, duplicate symbol or ISIN.
2. Match constituent ISIN to Upstox NSE equity instrument master; quarantine missing/ambiguous identities.
3. Retrieve coherent, sufficiently long, historical daily OHLCV for the mapped constituents. No silent partial-universe PASS.
4. Validate coverage, corporate-action adjustments, trading sessions and snapshot freshness. Until verified, results remain REVIEW, never certified PASS.
5. Compute frozen V1 cross-sectional momentum, breadth, independent price Trend Template, and candidate VCP research.
6. Publish **one** isolated EDGE snapshot to separate durable storage and make Streamlit read it automatically.
7. Verify end-to-end publication, market-data quality, UI, scheduled refresh and recovery. Only then claim operational.

No second universe, no brokerage orders, no change to original SPERA production.
