"""Isolated evening research publisher. Never writes verified data or D1."""
import json
import os
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo
import pandas as pd
from edge_core.upstox import fetch_daily_candles, fetch_intraday_daily_candle, reconcile_provisional_daily
from edge_core.ohlcv_integrity import snapshot_is_fresh
from edge_core.snapshot_integrity import validate_snapshot
from tools.publish_edge_snapshot import build


def publish_provisional(outdir="data/provisional", *, now=None, token=None,
                        daily_fetcher=fetch_daily_candles,
                        intraday_fetcher=fetch_intraday_daily_candle,
                        builder=build):
    destination = Path(outdir).resolve()
    verified = Path("data/latest").resolve()
    if destination == verified or verified in destination.parents or destination in verified.parents:
        raise ValueError("Provisional output must be isolated from verified data/latest")
    current = pd.Timestamp(now if now is not None else datetime.now(ZoneInfo("Asia/Kolkata")))
    if current.tzinfo is None:
        raise ValueError("Timezone-aware current time required")
    current = current.tz_convert("Asia/Kolkata")
    if current.hour < 16:
        raise ValueError("Provisional candles cannot be published before 16:00 IST")
    target = current.date()
    if not snapshot_is_fresh(target, current):
        raise ValueError("No completed trading session today; refusing provisional publication")
    token = token or os.getenv("UPSTOX_ACCESS_TOKEN") or os.getenv("UPSTOX_ANALYTIC_TOKEN")
    if not token:
        raise RuntimeError("Upstox token missing")
    def combined_fetcher(instrument_key, start_date, end_date, token=None):
        # Daily endpoint may include a current-day observation: explicitly
        # reconcile it with V3 provisional data rather than appending duplicates.
        history = daily_fetcher(instrument_key, start_date, target - timedelta(days=1), token=token)
        current_day = intraday_fetcher(instrument_key, target, token=token)
        return reconcile_provisional_daily(history, current_day, target)
    meta = builder(outdir=str(destination), token=token, fetcher=combined_fetcher)
    validate_snapshot(destination)
    if str(meta["last_session"]) != target.isoformat():
        raise ValueError("Provisional session not current; publication invalid")
    return meta


if __name__ == "__main__":
    print(json.dumps(publish_provisional(), indent=2))
