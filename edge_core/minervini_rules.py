"""Deterministic EDGE-specific Minervini-inspired research heuristics.

No discretionary SEPA certification; no brokerage execution.
"""
import math
import numpy as np
import pandas as pd


def trend_template(close, *, benchmark=None):
    """Nine explicit research gates; missing inputs fail closed."""
    prices = pd.to_numeric(pd.Series(close), errors="coerce").dropna()
    if len(prices) < 253 or (prices <= 0).any():
        return {"pass": False, "rules": [False] * 9, "status": "INSUFFICIENT_HISTORY"}
    p = float(prices.iloc[-1])
    sma50 = float(prices.tail(50).mean())
    sma150 = float(prices.tail(150).mean())
    sma200 = float(prices.tail(200).mean())
    sma200_prior = float(prices.iloc[-221:-21].mean())
    lo = float(prices.tail(252).min())
    hi = float(prices.tail(252).max())
    rules = [
        p > sma150,
        p > sma200,
        sma150 > sma200,
        sma200 > sma200_prior,
        sma50 > sma150,
        sma50 > sma200,
        p > sma50,
        p >= 1.30 * lo,
        p >= 0.75 * hi,
    ]
    return {"pass": all(rules), "rules": [bool(x) for x in rules],
            "status": "TREND_PASS" if all(rules) else "TREND_FAIL"}


def edge_rs_score(prices):
    """EDGE-specific 40/20/20/20 weighted 3/6/9/12-month returns."""
    series = pd.to_numeric(pd.Series(prices), errors="coerce")
    if len(series) < 253 or not np.isfinite(series.iloc[[-1, -64, -127, -190, -253]]).all():
        return np.nan
    last = float(series.iloc[-1])
    anchors = [float(series.iloc[-64]), float(series.iloc[-127]),
               float(series.iloc[-190]), float(series.iloc[-253])]
    if min(anchors) <= 0 or last <= 0:
        return np.nan
    return sum(weight * (last / anchor - 1) for weight, anchor in
               zip((0.4, 0.2, 0.2, 0.2), anchors))


def edge_rs_percentile(close):
    """Cross-sectional percentile across symbols with valid 253-session histories."""
    scores = {symbol: edge_rs_score(close[symbol]) for symbol in close.columns}
    values = pd.Series(scores, dtype=float)
    return (values.rank(pct=True, method="average") * 100).where(values.notna())


def vcp_three_contractions(high, low, volume, *, blocks=(35, 15, 5)):
    """Three strictly shrinking sequential ranges, with declining volume."""
    frames = [pd.to_numeric(pd.Series(v), errors="coerce") for v in (high, low, volume)]
    if len(set(map(len, frames))) != 1 or len(frames[0]) < sum(blocks):
        return {"status": "INSUFFICIENT_HISTORY", "pass": False}
    window = pd.DataFrame({"high": frames[0].to_numpy(),
                           "low": frames[1].to_numpy(),
                           "volume": frames[2].to_numpy()}).tail(sum(blocks))
    if not np.isfinite(window.to_numpy()).all() or (window.high <= 0).any() or (window.low <= 0).any() or (window.volume < 0).any() or (window.high < window.low).any():
        return {"status": "INVALID_CANDLES", "pass": False}
    spans = []
    vols = []
    offset = 0
    for size in blocks:
        segment = window.iloc[offset:offset + size]
        spans.append(float((segment.high.max() - segment.low.min()) / segment.high.max()))
        vols.append(float(segment.volume.mean()))
        offset += size
    passed = spans[0] > spans[1] > spans[2] and spans[2] <= 0.08 and vols[0] > vols[1] > vols[2]
    return {"status": "VCP_PASS" if passed else "VCP_FAIL", "pass": bool(passed),
            "contractions": spans, "average_volumes": vols}


def validate_stop_update(old_stop, proposed_stop, *, side="LONG"):
    """Reject widening before writing any event; long stop cannot decrease."""
    a, b = float(old_stop), float(proposed_stop)
    if not all(math.isfinite(x) and x > 0 for x in (a, b)):
        raise ValueError("Invalid stop")
    if side == "LONG" and b < a:
        raise ValueError("STOP_WIDENING_FORBIDDEN")
    if side == "SHORT" and b > a:
        raise ValueError("STOP_WIDENING_FORBIDDEN")
    if side not in ("LONG", "SHORT"):
        raise ValueError("Invalid position side")
    return True
