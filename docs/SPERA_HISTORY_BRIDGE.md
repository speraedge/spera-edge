# SPERA Wisdom → SPERA EDGE NIFTY 500 historical bridge

EDGE reads **only** trusted LIVE/PASS snapshots from the original SPERA Wisdom `weekly_snapshots` and `snapshot_chunks` D1 tables. Original storage is never modified.

## One-time setup in the EDGE repository
Set these three **EDGE GitHub Actions secrets** using the source Cloudflare account and D1 database identity:
- `SPERA_SOURCE_CF_ACCOUNT_ID`
- `SPERA_SOURCE_D1_DATABASE_ID`
- `SPERA_SOURCE_CF_READ_TOKEN` — a Cloudflare token limited to reading the source D1 database wherever supported; the importer additionally enforces SELECT-only queries. Never use or publish a token in source code.

From GitHub Actions run **Import trusted SPERA Wisdom NIFTY 500 history**, with weeks=7. This is deliberately manually triggered until source access and publication have been reviewed.

## Output
- `data/history/manifest.json`: actual verified week keys and provenance
- `data/history/nifty500_YYYY-MM-DD.csv`: historical cross-section for each week

The Leadership Scanner renders these historical weekly snapshots automatically after import. A missing week is not interpolated. No daily OHLCV, full Stage 2 certification, or current signal is inferred from historical momentum snapshots.

## Source contract
Original SPERA Wisdom `persistence.py` `SnapshotStore.assert_trusted` requires: READY display state, PASS snapshot freshness, PASS session authority, expected session=true, PASS corporate action authority, and pass_count>0. The bridge mirrors these conditions and requires source database rows freshness=PASS and source=LIVE. It does not claim to re-certify the original upstream inputs.

## Limits
Import requires access to the **original** Cloudflare D1 database. GitHub source-code access alone cannot retrieve private D1 records. The import has not run until GitHub Actions shows success. Keep the EDGE repo private if the historical exports should remain private.
