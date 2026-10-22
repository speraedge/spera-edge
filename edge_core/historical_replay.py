"""Deterministic OHLCV historical replay for EDGE breakout rule verification.

Uses an as-of prefix for each signal date. This is a technical-rule audit,
not a historical NIFTY membership reconstruction or an executable backtest.
"""
import numpy as np
import pandas as pd


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
    # Scan each symbol once; prior pivots and volume baselines are shifted to
    # exclude the candidate session, avoiding repeated full-universe replays.
    records = []
    for symbol in close.columns:
        c = pd.to_numeric(close[symbol], errors="coerce")
        h = pd.to_numeric(high[symbol], errors="coerce")
        l = pd.to_numeric(low[symbol], errors="coerce")
        v = pd.to_numeric(volume[symbol], errors="coerce")
        pivot = h.shift(1).rolling(20, min_periods=20).max()
        baseline = v.shift(1).rolling(50, min_periods=50).mean()
        stop = l.shift(1).rolling(10, min_periods=10).min()
        prior_valid = (c.gt(0) & h.gt(0) & v.ge(0)).shift(1).rolling(50, min_periods=50).sum().eq(50)
        prior_lows_valid = l.shift(1).gt(0).rolling(10, min_periods=10).sum().eq(10)
        candidates = c.gt(pivot) & v.ge(baseline * volume_multiple) & baseline.gt(0) & prior_valid & prior_lows_valid
        candidates &= c.gt(0) & h.ge(c) & l.gt(0) & l.le(c) & v.ge(0)
        for i in np.flatnonzero(candidates.to_numpy()):
            if i < 50 or not lower <= dates[i] <= upper:
                continue
            future = c.iloc[i+horizon] if i+horizon < len(c) else np.nan
            path = l.iloc[i+1:i+horizon+1]
            outcome, first_stop = "UNRESOLVED", None
            if i+horizon < len(c) and np.isfinite(future) and future > 0 and len(path) == horizon and np.isfinite(path).all() and path.gt(0).all():
                breaches = path <= stop.iloc[i]
                if breaches.any():
                    outcome = "STOP_BREACH"
                    first_stop = str(pd.Timestamp(path.index[np.flatnonzero(breaches.to_numpy())[0]]).date())
                else:
                    outcome = "SUCCESS" if future > c.iloc[i] and future >= pivot.iloc[i] else "FAILURE"
            records.append({"Symbol": symbol, "Session": str(dates[i].date()),
                            "Pivot": float(pivot.iloc[i]), "Breakout_Close": float(c.iloc[i]),
                            "Volume_Ratio": float(v.iloc[i] / baseline.iloc[i]),
                            "Stop": float(stop.iloc[i]), "Outcome": outcome,
                            "First_Stop_Session": first_stop})
    return pd.DataFrame(records, columns=["Symbol", "Session", "Pivot", "Breakout_Close",
                                          "Volume_Ratio", "Stop", "Outcome", "First_Stop_Session"])
