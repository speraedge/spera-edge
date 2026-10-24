"""On-demand, snapshot-bound OHLCV candlestick chart renderer.

No generated PNG is stored in Git or written to disk. The caller is
responsible for validating the saved snapshot before calling this module.
"""
from __future__ import annotations

from io import BytesIO
import logging

import pandas as pd


def render_validated_ohlcv_png(open_, high, low, close, volume, symbol, bars=260,
                              pivot=None, stop=None):
    import mplfinance as mpf
    if not isinstance(symbol, str) or not symbol:
        raise ValueError("Invalid symbol")
    if not 50 <= int(bars) <= 500:
        raise ValueError("Chart window must be 50–500 sessions")
    frames = (("Open", open_), ("High", high), ("Low", low),
              ("Close", close), ("Volume", volume))
    if any(symbol not in frame.columns for _, frame in frames):
        raise ValueError("Symbol missing from OHLCV")
    cleaned = {}
    for name, frame in frames:
        parsed = pd.to_datetime(frame.index, errors="coerce")
        if pd.isna(parsed).any():
            raise ValueError(f"Chart unavailable: invalid dates in {name}")
        if getattr(parsed, "tz", None) is not None:
            parsed = parsed.tz_localize(None)
        series = pd.Series(pd.to_numeric(frame[symbol], errors="coerce").to_numpy(),
                           index=pd.DatetimeIndex(parsed), name=name)
        if series.index.has_duplicates:
            raise ValueError(f"Chart unavailable: duplicate dates in {name}")
        cleaned[name] = series.sort_index().dropna()
    indexes = [series.index for series in cleaned.values()]
    if not all(index.equals(indexes[0]) for index in indexes[1:]):
        logging.warning("Chart OHLCV dates differ for %s; plotting intersection only", symbol)
    common = indexes[0]
    for index in indexes[1:]:
        common = common.intersection(index)
    common = common.sort_values()
    data = pd.DataFrame({name: series.reindex(common) for name, series in cleaned.items()})
    data = data.dropna().tail(int(bars))
    if len(data) < 50:
        raise ValueError("Insufficient aligned 50-session OHLCV history")
    if ((data["High"] < data[["Open", "Close", "Low"]].max(axis=1)) |
        (data["Low"] > data[["Open", "Close"]].min(axis=1)) |
        (data["Volume"] < 0)).any():
        raise ValueError("Invalid OHLCV candles")
    levels = []
    for level in (pivot, stop):
        if level is not None:
            level = float(level)
            if not 0 < level < float("inf"):
                raise ValueError("Invalid research level")
            levels.append(level)
    moving_averages = (50, 150, 200) if len(data) >= 200 else (50,)
    kwargs = {"type": "candle", "volume": True, "mav": moving_averages,
              "style": "yahoo", "returnfig": True, "figsize": (12, 7),
              "title": f"{symbol} | OHLCV research only"}
    if levels:
        kwargs["hlines"] = {"hlines": levels, "linestyle": "--", "alpha": 0.7}
    fig, _ = mpf.plot(data, **kwargs)
    buffer = BytesIO()
    fig.savefig(buffer, format="png", dpi=110, bbox_inches="tight")
    import matplotlib.pyplot as plt
    plt.close(fig)
    return buffer.getvalue()
