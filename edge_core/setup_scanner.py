"""setup_scanner.py - VCP / pullback setup scanner.

Answers the "WHEN" question that the Momentum V1 contract reserves for
technical setups:

  * Momentum rank answers: which stocks are strong?
  * This module answers: which of those are currently coiled?

It is a pure function layer. No I/O, no Streamlit, no side effects.
It does NOT change Pure_Momentum_Rank, Inst_Rank, trust states, or the
Strict Watchlist. It only produces a diagnostic DataFrame that the app
displays in a separate tab.

Inputs:
    close_df / volume_df / high_df / low_df: DataFrames indexed by date,
        columns "SYMBOL.NS". Real OHLC and volume are required; missing values
        are not fabricated.
    symbols  : optional list of symbols (without .NS suffix) to restrict to

Output:
    DataFrame with one row per qualifying symbol and these columns:
        Ticker, VCP_Setup, VCP_Score, ATR_Pct, Range_10, Range_20,
        Range_40, Avg_Daily_Volume10, Avg_Daily_Volume20, Return_6M, Return_12M,
        Distance_From_High, Avg_Traded_Value20
"""

from __future__ import annotations

import numpy as np
import pandas as pd

ATR_PERIOD = 14
EMA_PERIOD = 20
VOLUME_PERIOD = 20
MIN_HISTORY = 253


def _indicators_one_stock(close_s: pd.Series, volume_s: pd.Series,
                          high_s: pd.Series, low_s: pd.Series) -> pd.DataFrame:
    """Compute VCP indicators only on sessions with real OHLCV data."""
    df = pd.DataFrame({
        "close": close_s, "volume": volume_s, "high": high_s, "low": low_s,
    }).dropna()
    if len(df) < MIN_HISTORY:
        return pd.DataFrame()

    # Moving averages
    df["ema20"] = df["close"].ewm(span=EMA_PERIOD, adjust=False).mean()
    df["sma50"] = df["close"].rolling(50).mean()
    df["sma200"] = df["close"].rolling(200).mean()

    # True Range
    high = df["high"]
    low = df["low"]
    prev_close = df["close"].shift(1)
    r1 = high - low
    r2 = (high - prev_close).abs()
    r3 = (low - prev_close).abs()
    df["true_range"] = pd.concat([r1, r2, r3], axis=1).max(axis=1)
    df["atr14"] = df["true_range"].rolling(ATR_PERIOD).mean()
    df["atr_percent"] = df["atr14"] / df["close"] * 100.0

    # Volume averages
    df["avg_volume10"] = df["volume"].rolling(10).mean()
    df["avg_volume20"] = df["volume"].rolling(VOLUME_PERIOD).mean()

    # Traded value
    df["traded_value"] = df["close"] * df["volume"]
    df["avg_traded_value20"] = df["traded_value"].rolling(20).mean()

    # Price range contraction includes intraday extremes.
    df["range_10"] = (
        df["high"].rolling(10).max() - df["low"].rolling(10).min()
    ) / df["close"]
    df["range_20"] = (
        df["high"].rolling(20).max() - df["low"].rolling(20).min()
    ) / df["close"]
    df["range_40"] = (
        df["high"].rolling(40).max() - df["low"].rolling(40).min()
    ) / df["close"]

    # Returns
    df["return_1m"] = (df["close"] / df["close"].shift(21) - 1.0) * 100.0
    df["return_6m"] = (df["close"] / df["close"].shift(126) - 1.0) * 100.0
    df["return_12m"] = (df["close"] / df["close"].shift(252) - 1.0) * 100.0

    # 52-week high from daily highs.
    df["high_52w"] = df["high"].rolling(252).max()
    df["distance_from_high"] = (df["close"] / df["high_52w"] - 1.0) * 100.0

    # Lagged values for contraction checks
    df["atr_percent_10_days_ago"] = df["atr_percent"].shift(10)
    df["atr_percent_20_days_ago"] = df["atr_percent"].shift(20)
    df["avg_volume10_10_days_ago"] = df["avg_volume10"].shift(10)
    df["avg_volume10_20_days_ago"] = df["avg_volume10"].shift(20)

    return df


def _evaluate_setups(df: pd.DataFrame) -> pd.DataFrame:
    """Apply the qualification flags and score to one stock's indicator frame."""
    if df is None or df.empty:
        return df

    # 1. Strong uptrend
    df["uptrend"] = (
        (df["close"] > df["ema20"])
        & (df["close"] > df["sma50"])
        & (df["sma50"] > df["sma200"])
        & (df["sma200"] > df["sma200"].shift(20))
    )

    # 2. ATR percentage declining
    df["atr_declining"] = (
        (df["atr_percent"] < df["atr_percent_10_days_ago"])
        & (df["atr_percent_10_days_ago"] < df["atr_percent_20_days_ago"])
    )

    # 3. Volume contraction is direction-neutral; volume alone cannot identify
    # whether the activity was buying or selling.
    df["volume_contracting"] = (
        (df["avg_volume10"] < df["avg_volume10_10_days_ago"])
        & (df["avg_volume10_10_days_ago"] < df["avg_volume10_20_days_ago"])
    )

    # 4. VCP contraction
    df["vcp_contraction"] = (
        (df["range_10"] < df["range_20"])
        & (df["range_20"] < df["range_40"])
    )

    # 5. Tight consolidation
    df["tight_consolidation"] = df["range_10"] <= 0.08

    # 6. Controlled pullback
    df["controlled_pullback"] = (
        (df["close"] > df["sma50"])
        & (df["close"].rolling(5).min() <= df["ema20"])
        & (df["close"] >= df["sma50"] * 0.97)
    )

    # 7. Near 52-week high
    df["near_52_week_high"] = df["distance_from_high"] >= -20.0

    # 9. Price setup
    df["price_setup"] = (
        df["vcp_contraction"] | df["tight_consolidation"] | df["controlled_pullback"]
    )

    # 10. Final qualification
    df["qualified"] = (
        df["uptrend"]
        & df["atr_declining"]
        & df["volume_contracting"]
        & df["price_setup"]
        & df["near_52_week_high"]
    )

    return df


def _setup_label(row: pd.Series) -> str:
    setups = []
    if row.get("vcp_contraction"):
        setups.append("VCP")
    if row.get("tight_consolidation"):
        setups.append("Tight Consolidation")
    if row.get("controlled_pullback"):
        setups.append("Controlled Pullback")
    return ", ".join(setups) if setups else ""


def _score(row: pd.Series) -> int:
    s = 0
    s += int(bool(row.get("vcp_contraction"))) * 3
    s += int(bool(row.get("tight_consolidation"))) * 2
    s += int(bool(row.get("controlled_pullback"))) * 2
    s += int(bool(row.get("atr_declining"))) * 2
    s += int(bool(row.get("volume_contracting"))) * 2
    s += int(bool(row.get("uptrend"))) * 2
    return s


def setup_scanner_coverage(close_df: pd.DataFrame,
                           volume_df: pd.DataFrame | None,
                           high_df: pd.DataFrame | None,
                           low_df: pd.DataFrame | None,
                           symbols: list | None = None) -> dict:
    """Summarize how many requested symbols have enough aligned OHLCV history."""
    if close_df is None or close_df.empty:
        return {
            "symbols_examined": 0,
            "symbols_with_sufficient_history": 0,
            "symbols_with_short_history": 0,
            "symbols_missing_ohlcv": 0,
        }

    if symbols is None:
        columns = list(close_df.columns)
    else:
        columns = [str(s) if str(s) in close_df.columns else f"{s}.NS" for s in symbols]
        columns = [col for col in columns if col in close_df.columns]

    frames = (volume_df, high_df, low_df)
    sufficient = short = missing = 0
    for col in columns:
        if any(frame is None or frame.empty or col not in frame.columns for frame in frames):
            missing += 1
            continue
        close_s = pd.to_numeric(close_df[col], errors="coerce").dropna().sort_index()
        aligned = pd.concat(
            [
                close_s,
                pd.to_numeric(volume_df[col].reindex(close_s.index), errors="coerce"),
                pd.to_numeric(high_df[col].reindex(close_s.index), errors="coerce"),
                pd.to_numeric(low_df[col].reindex(close_s.index), errors="coerce"),
            ],
            axis=1,
        ).dropna()
        if len(aligned) >= MIN_HISTORY:
            sufficient += 1
        else:
            short += 1

    return {
        "symbols_examined": len(columns),
        "symbols_with_sufficient_history": sufficient,
        "symbols_with_short_history": short,
        "symbols_missing_ohlcv": missing,
    }


def compute_setup_scanner(close_df: pd.DataFrame,
                          volume_df: pd.DataFrame | None,
                          symbols: list | None = None,
                          high_df: pd.DataFrame | None = None,
                          low_df: pd.DataFrame | None = None) -> pd.DataFrame:
    """Return VCP setup results for the current universe.

    All input frames are indexed by date with columns "SYMBOL.NS". OHLCV
    inputs are required so the scanner cannot substitute fabricated data.
    """
    if close_df is None or close_df.empty:
        return pd.DataFrame()
    if volume_df is None or volume_df.empty:
        raise ValueError("Setup Scanner requires real volume data; volume is unavailable.")
    if high_df is None or high_df.empty or low_df is None or low_df.empty:
        raise ValueError("Setup Scanner requires real high and low price data.")

    if symbols is None:
        columns = list(close_df.columns)
    else:
        columns = [str(s) if str(s) in close_df.columns else f"{s}.NS" for s in symbols]
        columns = [c for c in columns if c in close_df.columns]

    rows = []
    for col in columns:
        close_s = close_df[col].dropna().astype(float).sort_index()
        if close_s.empty:
            continue
        if col not in volume_df.columns or col not in high_df.columns or col not in low_df.columns:
            continue
        volume_s = pd.to_numeric(volume_df[col].reindex(close_s.index), errors="coerce")
        high_s = pd.to_numeric(high_df[col].reindex(close_s.index), errors="coerce")
        low_s = pd.to_numeric(low_df[col].reindex(close_s.index), errors="coerce")

        stock_df = _indicators_one_stock(close_s, volume_s, high_s, low_s)
        if stock_df.empty:
            continue
        stock_df = _evaluate_setups(stock_df)
        if stock_df.empty or not stock_df["qualified"].iloc[-1]:
            continue

        last = stock_df.iloc[-1]
        rows.append({
            "Ticker": col.replace(".NS", ""),
            "VCP_Setup": _setup_label(last),
            "VCP_Score": _score(last),
            "VCP_Score_Max": 13,
            "Uptrend": bool(last.get("uptrend")),
            "ATR_Contracting": bool(last.get("atr_declining")),
            "Volume_Contracting": bool(last.get("volume_contracting")),
            "VCP_Contraction": bool(last.get("vcp_contraction")),
            "Tight_Consolidation": bool(last.get("tight_consolidation")),
            "Controlled_Pullback": bool(last.get("controlled_pullback")),
            "Last_Price": last.get("close"),
            "ATR_Pct": last.get("atr_percent"),
            "Range_10": last.get("range_10"),
            "Range_20": last.get("range_20"),
            "Range_40": last.get("range_40"),
            "Avg_Daily_Volume10": last.get("avg_volume10"),
            "Avg_Daily_Volume20": last.get("avg_volume20"),
            "Return_6M": last.get("return_6m") / 100.0 if pd.notna(last.get("return_6m")) else np.nan,
            "Return_12M": last.get("return_12m") / 100.0 if pd.notna(last.get("return_12m")) else np.nan,
            "Distance_From_High": last.get("distance_from_high") / 100.0 if pd.notna(last.get("distance_from_high")) else np.nan,
            "Avg_Traded_Value20": last.get("avg_traded_value20"),
        })

    if not rows:
        return pd.DataFrame(columns=[
            "Ticker", "VCP_Setup", "VCP_Score", "ATR_Pct",
            "Range_10", "Range_20", "Range_40",
            "Avg_Daily_Volume10", "Avg_Daily_Volume20",
            "Return_6M", "Return_12M", "Distance_From_High",
            "Avg_Traded_Value20", "Last_Price", "VCP_Score_Max",
            "Uptrend", "ATR_Contracting", "Volume_Contracting",
            "VCP_Contraction", "Tight_Consolidation", "Controlled_Pullback",
        ])

    out = pd.DataFrame(rows)
    out = out.sort_values(
        ["VCP_Score", "Return_6M"], ascending=[False, False]
    ).reset_index(drop=True)
    return out


# Full-universe fail-closed audit; the filtered setup scanner above remains
# available for backward-compatible research exports.
SETUP_RULES = ("uptrend", "atr_declining", "volume_contracting",
               "vcp_contraction", "tight_consolidation", "near_52_week_high")

def setup_qualification_diagnostics(close_df, volume_df, high_df, low_df):
    """One shared strict VCP definition, with reasons for every symbol.

    A controlled pullback is not a VCP. No threshold is relaxed here.
    """
    rows = []
    for symbol in close_df.columns:
        row = {"Symbol": symbol, "Setup_Qualified": False,
               "Setup_Fail_Reasons": "INSUFFICIENT_OHLCV"}
        if any(frame is None or symbol not in frame.columns for frame in
               (volume_df, high_df, low_df)):
            rows.append(row)
            continue
        frame = _indicators_one_stock(
            pd.to_numeric(close_df[symbol], errors="coerce").sort_index(),
            pd.to_numeric(volume_df[symbol], errors="coerce").sort_index(),
            pd.to_numeric(high_df[symbol], errors="coerce").sort_index(),
            pd.to_numeric(low_df[symbol], errors="coerce").sort_index())
        if frame.empty:
            rows.append(row)
            continue
        last = _evaluate_setups(frame).iloc[-1]
        flags = {
            "uptrend": bool(last["uptrend"]),
            "atr_declining": bool(last["atr_declining"]),
            "volume_contracting": bool(last["volume_contracting"]),
            "vcp_contraction": bool(last["vcp_contraction"]),
            "tight_consolidation": bool(last["tight_consolidation"]),
            "near_52_week_high": bool(last["near_52_week_high"]),
        }
        # Require the contraction pattern, not the scanner's alternative
        # tight-consolidation / controlled-pullback setup families.
        qualified = all(flags[k] for k in
                        ("uptrend", "atr_declining", "volume_contracting",
                         "vcp_contraction", "near_52_week_high"))
        failed = [key.upper() + "_FAIL" for key in
                  ("uptrend", "atr_declining", "volume_contracting",
                   "vcp_contraction", "near_52_week_high") if not flags[key]]
        row.update(Setup_Qualified=qualified,
                   Setup_Fail_Reasons="PASS" if qualified else "|".join(failed),
                   **{"Setup_" + k: v for k, v in flags.items()})
        rows.append(row)
    return pd.DataFrame(rows)
