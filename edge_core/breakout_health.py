"""Research-only, forward-measured breakout health; never a trading signal."""
import numpy as np
import pandas as pd


def breakout_health(close, high, volume, *, horizon=10, lookback=80, volume_multiple=1.5, low=None):
    """Qualified prior-20-session high breakouts; evaluate after horizon sessions.

    Uses only information known at each candidate session. Success means
    horizon close > breakout close and >= original pivot; failure otherwise.
    Unresolved events are excluded from outcome rates. Same-symbol events
    have a horizon-session cooldown to avoid counting one breakout repeatedly.
    """
    frames = (close, high, volume) if low is None else (close, high, volume, low)
    if any(not x.index.equals(close.index) or not x.columns.equals(close.columns) for x in frames):
        raise ValueError("Aligned OHLCV required")
    if close.index.has_duplicates or close.columns.has_duplicates or not close.index.is_monotonic_increasing:
        raise ValueError("Unique sorted sessions and symbols required")
    if not 1 <= horizon <= 60 or not 1 <= lookback <= 252 or not np.isfinite(volume_multiple) or volume_multiple <= 0:
        raise ValueError("Invalid research parameters")
    events = []
    if len(close) < 52:
        return {"qualified": 0, "resolved": 0, "successes": 0, "failures": 0,
                "unresolved": 0, "success_rate_pct": None, "stop_breaches": 0, "events": pd.DataFrame()}
    start = max(50, len(close) - lookback)
    for symbol in close.columns:
        c = pd.to_numeric(close[symbol], errors="coerce")
        h = pd.to_numeric(high[symbol], errors="coerce")
        v = pd.to_numeric(volume[symbol], errors="coerce")
        lows = pd.to_numeric(low[symbol], errors="coerce") if low is not None else None
        last_event = -horizon - 1
        for i in range(start, len(c)):
            if i - last_event <= horizon:
                continue
            prior_c, prior_h, prior_v = c.iloc[i-50:i], h.iloc[i-20:i], v.iloc[i-50:i]
            today = (c.iloc[i], h.iloc[i], v.iloc[i])
            if (not np.isfinite(today).all() or not np.isfinite(prior_c).all()
                    or not np.isfinite(prior_h).all() or not np.isfinite(prior_v).all()
                    or min(today) < 0 or c.iloc[i] <= 0 or (prior_h <= 0).any()
                    or (prior_v < 0).any() or (prior_c <= 0).any()):
                continue
            pivot = float(prior_h.max())
            baseline = float(prior_v.mean())
            if baseline <= 0 or c.iloc[i] <= pivot or v.iloc[i] < baseline * volume_multiple:
                continue
            last_event = i
            stop_window = lows.iloc[i-10:i] if lows is not None else None
            stop = float(stop_window.min()) if stop_window is not None and np.isfinite(stop_window).all() and (stop_window > 0).all() else None
            resolved = i + horizon < len(c)
            outcome = "UNRESOLVED"
            future = None
            stop_breached = None
            first_stop_session = None
            if resolved:
                if lows is not None:
                    path = lows.iloc[i+1:i+horizon+1]
                    if stop is not None and np.isfinite(path).all() and (path > 0).all():
                        breached = path <= stop
                        stop_breached = bool(breached.any())
                        if stop_breached:
                            first_stop_session = str(pd.Timestamp(path.index[np.flatnonzero(breached.to_numpy())[0]]).date())
                future = float(c.iloc[i+horizon])
                if not np.isfinite(future) or future <= 0:
                    outcome = "UNRESOLVED"
                else:
                    outcome = ("STOP_BREACH" if stop_breached is True else
                               "UNRESOLVED" if lows is not None and stop_breached is None else
                               "SUCCESS" if future > c.iloc[i] and future >= pivot else "FAILURE")
            events.append({"Symbol": symbol, "Session": str(pd.Timestamp(c.index[i]).date()),
                           "Pivot": pivot, "Breakout_Close": float(c.iloc[i]),
                           "Volume_Ratio": float(v.iloc[i] / baseline),
                           "Evaluation_Close": future, "Stop": stop,
                           "Stop_Breached": stop_breached, "First_Stop_Session": first_stop_session,
                           "Outcome": outcome})
    frame = pd.DataFrame(events, columns=["Symbol", "Session", "Pivot", "Breakout_Close",
                                         "Volume_Ratio", "Evaluation_Close", "Stop", "Stop_Breached", "First_Stop_Session", "Outcome"])
    successes = int((frame["Outcome"] == "SUCCESS").sum())
    breaches = int((frame["Outcome"] == "STOP_BREACH").sum())
    failures = int((frame["Outcome"] == "FAILURE").sum()) + breaches
    resolved = successes + failures
    return {"qualified": len(frame), "resolved": resolved, "successes": successes,
            "failures": failures, "stop_breaches": breaches, "unresolved": len(frame)-resolved,
            "success_rate_pct": round(100*successes/resolved, 1) if resolved else None,
            "events": frame}


def breakout_horizon_comparison(close, high, volume, *, low, horizons=(5, 10, 20), lookback=80):
    """Compare independently evaluated fixed-horizon research cohorts.

    Each horizon has its own event cooldown and may therefore have a different
    denominator; rates must not be interpreted as the same trade cohort.
    """
    if not horizons or len(set(horizons)) != len(horizons):
        raise ValueError("Distinct horizons required")
    rows = []
    for horizon in horizons:
        result = breakout_health(close, high, volume, low=low,
                                 horizon=horizon, lookback=lookback)
        rows.append({"Horizon_Sessions": horizon,
                     "Qualified": result["qualified"], "Resolved": result["resolved"],
                     "Successes": result["successes"], "Failures": result["failures"],
                     "Stop_Breaches": result["stop_breaches"],
                     "Unresolved": result["unresolved"],
                     "Success_Rate_Pct": result["success_rate_pct"]})
    return pd.DataFrame(rows)
