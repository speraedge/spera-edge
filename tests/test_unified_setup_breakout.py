"""Regression checks for unified setup vs breakout research states."""
import numpy as np
import pandas as pd

from edge_core.setup_scanner import setup_qualification_diagnostics
from edge_workspace import entry_diagnostics


def _sample():
    dates = pd.bdate_range("2025-01-01", periods=260)
    prices = pd.Series(np.linspace(100, 160, 260), index=dates)
    close = pd.DataFrame({"BATAINDIA": prices})
    high = close * 1.01
    low = close * 0.99
    volume = pd.DataFrame({"BATAINDIA": np.full(260, 1000.0)}, index=dates)
    # Force a breakout on 1.5x volume without volume contraction.
    close.iloc[-1, 0] = 180
    high.iloc[-1, 0] = 181
    low.iloc[-1, 0] = 179
    volume.iloc[-1, 0] = 3000
    return close, high, low, volume


def test_breakout_only_is_not_qualified_setup():
    close, high, low, volume = _sample()
    setup = setup_qualification_diagnostics(close, volume, high, low).iloc[0]
    entry = entry_diagnostics(close, high, low, volume, close.index[-1]).iloc[0]
    assert not bool(setup["Setup_Qualified"])
    assert "VOLUME_CONTRACTING_FAIL" in setup["Setup_Fail_Reasons"]
    assert bool(entry["Breakout_Confirmed"])
    assert not bool(entry["Setup_Qualified"])
    assert not bool(entry["Technical_Entry_Review"])
    assert entry["Entry_Classification"] == "BREAKOUT_ONLY_REVIEW"


def test_insufficient_history_fails_closed():
    close, high, low, volume = _sample()
    short = setup_qualification_diagnostics(close.tail(60), volume.tail(60), high.tail(60), low.tail(60))
    assert short.iloc[0]["Setup_Fail_Reasons"] == "INSUFFICIENT_OHLCV"
    assert not bool(short.iloc[0]["Setup_Qualified"])


def test_missing_latest_price_remains_unconfirmed():
    close, high, low, volume = _sample()
    close.iloc[-1, 0] = np.nan
    entry = entry_diagnostics(close, high, low, volume, close.index[-1]).iloc[0]
    assert entry["Evidence"] == "INCOMPLETE_OHLCV"
    assert not bool(entry["Setup_Qualified"])
    assert not bool(entry["Breakout_Confirmed"])
    assert not bool(entry["Technical_Entry_Review"])
    assert entry["Entry_Classification"] == "NOT_QUALIFIED"
