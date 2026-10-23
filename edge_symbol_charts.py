"""On-demand, snapshot-bound OHLCV candlestick chart renderer.

No generated PNG is stored in Git or written to disk. The caller is
responsible for validating the saved snapshot before calling this module.
"""
from __future__ import annotations

from io import BytesIO

import pandas as pd


def render_symbol_png(close, high, low, volume, symbol, pivot=None, stop=None, bars=260):
    import mplfinance as mpf
    if not isinstance(symbol, str) or not symbol or symbol not in close.columns:
        raise ValueError("Symbol missing from validated OHLCV snapshot")
    if not 60 <= int(bars) <= 500:
        raise ValueError("Chart window must be 60–500 sessions")
    series = {}
    for name, frame in (("Close", close), ("High", high), ("Low", low), ("Volume", volume)):
        if symbol not in frame:
            raise ValueError("Missing symbol in " + name)
        series[name] = pd.to_numeric(frame[symbol], errors="coerce")
    data = pd.DataFrame(series).dropna().sort_index().tail(int(bars))
    if len(data) < 50 or not isinstance(data.index, pd.DatetimeIndex):
        raise ValueError("Insufficient aligned chart history")
    if ((data["High"] < data[["Low", "Close"]].max(axis=1)) |
        (data["Low"] > data["Close"]) | (data["Volume"] < 0)).any():
        raise ValueError("Invalid OHLCV candles")
    # Open is not supplied by the legacy snapshot reader: load the actual
    # validated open.csv separately; never synthesize an opening price.
    raise ValueError("Actual validated open prices required for candlesticks")


def render_validated_ohlcv_png(open_, high, low, close, volume, symbol, bars=260,
                              pivot=None, stop=None):
    import mplfinance as mpf
    if not isinstance(symbol, str) or not symbol:
        raise ValueError("Invalid symbol")
    if not 60 <= int(bars) <= 500:
        raise ValueError("Chart window must be 60–500 sessions")
    frames = (("Open", open_), ("High", high), ("Low", low),
              ("Close", close), ("Volume", volume))
    if any(symbol not in frame.columns for _, frame in frames):
        raise ValueError("Symbol missing from OHLCV")
    data = pd.DataFrame({name: pd.to_numeric(frame[symbol], errors="coerce")
                         for name, frame in frames}).sort_index().tail(int(bars))
    if not isinstance(data.index, pd.DatetimeIndex) or data.isna().any().any() or len(data) < 200:
        raise ValueError("Insufficient aligned 200-session OHLCV history")
    if ((data["High"] < data[["Open", "Close", "Low"]].max(axis=1)) |
        (data["Low"] > data[["Open", "Close"]].min(axis=1)) |
        (data["Volume"] < 0)).any():
        raise ValueError("Invalid OHLCV candles")
    if not all(frame.index.equals(close.index) for _, frame in frames):
        raise ValueError("Misaligned OHLCV dates")
    levels = []
    for level in (pivot, stop):
        if level is not None:
            level = float(level)
            if not 0 < level < float("inf"):
                raise ValueError("Invalid research level")
            levels.append(level)
    kwargs = {"type": "candle", "volume": True, "mav": (50, 150, 200),
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
