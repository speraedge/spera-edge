"""Conservative OHLCV quality gate. No price repair or ranking modification."""
import pandas as pd
import numpy as np


def audit_ohlcv(close, high, low, volume, *, expected_last_session=None):
    """Fail closed on invalid observed candles and mismatched time series.

    Missing values are reported separately because listing dates and suspended
    securities can produce genuine gaps. The caller decides coverage policy.
    """
    frames = {"close": close, "high": high, "low": low, "volume": volume}
    if any(not isinstance(df, pd.DataFrame) or df.empty for df in frames.values()):
        raise ValueError("All four OHLCV frames must be nonempty DataFrames")
    reference = close
    if reference.index.has_duplicates or reference.columns.has_duplicates:
        raise ValueError("Duplicate OHLCV dates or symbols")
    if not reference.index.is_monotonic_increasing:
        raise ValueError("OHLCV sessions must be chronological")
    sessions = pd.to_datetime(reference.index, errors="coerce")
    if sessions.isna().any() or sessions.has_duplicates:
        raise ValueError("Invalid or duplicate session dates")
    if (sessions.dayofweek >= 5).any():
        raise ValueError("Weekend trading session in daily OHLCV")
    if expected_last_session is not None:
        expected = pd.Timestamp(expected_last_session).date()
        if sessions[-1].date() != expected:
            raise ValueError("Last OHLCV session differs from metadata")
    for name, frame in frames.items():
        if not frame.index.equals(reference.index) or not frame.columns.equals(reference.columns):
            raise ValueError("Misaligned OHLCV: " + name)
        if any(not isinstance(symbol, str) or not symbol.strip() for symbol in frame.columns):
            raise ValueError("Invalid OHLCV symbol")
    numbers = {name: frame.apply(pd.to_numeric, errors="coerce") for name, frame in frames.items()}
    for name, frame in frames.items():
        bad = frame.notna() & numbers[name].isna()
        if bad.to_numpy().any():
            raise ValueError("Non-numeric observed OHLCV: " + name)
    for name, frame in numbers.items():
        if frame.notna().to_numpy().any() and not np.isfinite(frame.to_numpy(dtype=float)[frame.notna().to_numpy()]).all():
            raise ValueError("Non-finite observed OHLCV: " + name)
    observed = numbers["close"].notna() & numbers["high"].notna() & numbers["low"].notna() & numbers["volume"].notna()
    partial = sum(frame.notna() for frame in numbers.values())
    if ((partial > 0) & (partial < 4)).to_numpy().any():
        raise ValueError("Partially populated OHLCV candle")
    c, h, l, v = (numbers[name] for name in ("close", "high", "low", "volume"))
    invalid = observed & ((c <= 0) | (h <= 0) | (l <= 0) | (v < 0) |
                          (h < l) | (h < c) | (l > c))
    if invalid.to_numpy().any():
        raise ValueError("Invalid price, volume or candle high/low bounds")
    return {"sessions": len(reference), "symbols": len(reference.columns),
            "observed_candles": int(observed.to_numpy().sum()),
            "missing_candles": int((~observed).to_numpy().sum()),
            "first_session": str(sessions[0].date()),
            "last_session": str(sessions[-1].date()),
            "certified": False,
            "limitations": ["No independent corporate-action adjustment verification",
                            "No historical point-in-time membership verification",
                            "Missing candle coverage needs independent policy"]}
