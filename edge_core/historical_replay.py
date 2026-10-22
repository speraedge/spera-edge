"""Deterministic OHLCV historical replay for EDGE breakout rule verification.

Uses an as-of prefix for each signal date. This is a technical-rule audit,
not a historical NIFTY membership reconstruction or an executable backtest.
"""
import numpy as np
import pandas as pd
from edge_core.breakout_health import breakout_health


def replay_breakout_rules(close, high, low, volume, *, start=None, end=None,
                          horizon=10, volume_multiple=1.5):
    frames = (close, high, low, volume)
    if any(not f.index.equals(close.index) or not f.columns.equals(close.columns) for f in frames):
        raise ValueError("OHLCV frames must align")
    if close.index.has_duplicates or close.columns.has_duplicates or not close.index.is_monotonic_increasing:
        raise ValueError("Unique sorted OHLCV sessions required")
    dates = pd.to_datetime(close.index)
    if len(dates) < 51:
        return pd.DataFrame(columns=["Symbol", "Session", "Pivot", "Breakout_Close",
                                     "Volume_Ratio", "Stop", "Outcome", "First_Stop_Session"])
    lower = pd.Timestamp(start) if start is not None else dates[50]
    upper = pd.Timestamp(end) if end is not None else dates[-1]
    if lower > upper:
        raise ValueError("Start after end")
    records = []
    for i in range(50, len(dates)):
        if not lower <= dates[i] <= upper:
            continue
        # The prefix is the only price data the signal detection can inspect.
        prefix = slice(0, i+1)
        candidate = breakout_health(close.iloc[prefix], high.iloc[prefix],
                                    volume.iloc[prefix], low=low.iloc[prefix],
                                    horizon=horizon, lookback=1,
                                    volume_multiple=volume_multiple)["events"]
        if candidate.empty:
            continue
        for _, event in candidate.iterrows():
            symbol = event["Symbol"]
            future = close[symbol].iloc[i+horizon] if i+horizon < len(close) else np.nan
            path = pd.to_numeric(low[symbol].iloc[i+1:i+horizon+1], errors="coerce")
            stop = event["Stop"]
            outcome = "UNRESOLVED"
            first_stop = None
            if i+horizon < len(close) and pd.notna(future) and np.isfinite(future) and future > 0:
                if stop is not None and np.isfinite(stop) and len(path) == horizon and np.isfinite(path).all() and (path > 0).all():
                    breaches = path <= stop
                    if breaches.any():
                        outcome = "STOP_BREACH"
                        first_stop = str(pd.Timestamp(path.index[np.flatnonzero(breaches.to_numpy())[0]]).date())
                    else:
                        outcome = "SUCCESS" if future > event["Breakout_Close"] and future >= event["Pivot"] else "FAILURE"
            records.append({"Symbol": symbol, "Session": event["Session"],
                            "Pivot": event["Pivot"], "Breakout_Close": event["Breakout_Close"],
                            "Volume_Ratio": event["Volume_Ratio"], "Stop": stop,
                            "Outcome": outcome, "First_Stop_Session": first_stop})
    return pd.DataFrame(records, columns=["Symbol", "Session", "Pivot", "Breakout_Close",
                                          "Volume_Ratio", "Stop", "Outcome", "First_Stop_Session"])
