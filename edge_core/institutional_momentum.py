"""Institutional Momentum V2 - Spera Wealth Momentum Screener.

Adds professional momentum signals on top of the frozen Momentum V1 contract:
  - 12-1 momentum (skip most recent month)
  - Residual momentum (beta-adjusted)
  - Path quality / frog-in-the-pan
  - Idiosyncratic volatility penalty
  - Crowding proxy penalty
  - Volatility regime overlay

Pure pandas/numpy. No Streamlit. No I/O. No side effects.

Revision notes (vs the first V2 draft):
  * Path quality is now SIGNED. The old unsigned R2 scored a smoothly FALLING stock
    as high as a smoothly rising one. Composite uses Path_Signed_R2 = R2 x sign(slope).
    Path_Trend_R2 (unsigned) and Path_Positive_Ratio stay as display-only columns.
  * Inputs are winsorized (default 1%/99%) before z-scoring so one +300% small-cap
    cannot dominate a cross-section. V1 is frozen and is NOT winsorized.
  * Crowding_Stock is a 60-session CO-MOVEMENT proxy (mean pairwise correlation).
    It is not a holdings/flow-based crowding measure; the column name is kept only
    for compatibility.
  * Unknown regime now sizes at MULT_UNKNOWN (conservative) instead of full size.
  * Inst_Rank_PASS ranks Data_Quality == PASS rows only (the trusted watchlist).
"""

from __future__ import annotations
import numpy as np
import pandas as pd

SESSIONS_1M = 21
SESSIONS_3M = 63
SESSIONS_6M = 126
SESSIONS_12M = 252
SKIP_SESSIONS = SESSIONS_1M
FORMATION_WINDOW = SESSIONS_12M - SKIP_SESSIONS
SESSIONS_55D = 55
EMA_PERIODS = (21, 55, 100, 200)

W_12_1 = 0.50
W_RESIDUAL = 0.25
W_PATH = 0.15
W_IVOL_PENALTY = -0.05
W_CROWDING_PENALTY = -0.05

VOL_LOW = 0.15
VOL_MODERATE = 0.25
VOL_HIGH = 0.35
MULT_FULL = 1.0
MULT_MODERATE = 0.7
MULT_DEFENSIVE = 0.4
MULT_FLAT = 0.0
MULT_UNKNOWN = MULT_MODERATE   # fail conservative when the regime cannot be computed
WINSOR_LIMIT = 0.01


def _log_returns(close_series):
    if close_series is None or len(close_series) < 2:
        return pd.Series(dtype=float)
    s = close_series.dropna().astype(float).sort_index()
    return np.log(s / s.shift(1)).dropna()


def _align_returns(stock_close, market_close):
    sr = _log_returns(stock_close)
    mr = _log_returns(market_close)
    if sr.empty or mr.empty:
        return sr, mr
    df = pd.concat([sr.rename("s"), mr.rename("m")], axis=1).dropna()
    return df["s"], df["m"]


def _zscore(series, mask=None, winsor=WINSOR_LIMIT):
    if mask is None:
        mask = series.notna()
    s = pd.to_numeric(series, errors="coerce")
    if winsor and mask.sum() >= 20:
        lo, hi = s[mask].quantile(winsor), s[mask].quantile(1.0 - winsor)
        s = s.clip(lower=lo, upper=hi)
    mean = s[mask].mean()
    std = s[mask].std()
    if not np.isfinite(std) or std <= 0:
        return pd.Series(np.nan, index=series.index)
    return ((s - mean) / std).where(mask)


def compute_12_1_momentum(close_series):
    s = close_series.dropna().astype(float).sort_index()
    if len(s) < SESSIONS_12M + 1:
        return np.nan
    end_idx = len(s) - SKIP_SESSIONS - 1
    start_idx = len(s) - SESSIONS_12M - 1
    if start_idx < 0 or end_idx <= start_idx:
        return np.nan
    p_start = float(s.iloc[start_idx])
    p_end = float(s.iloc[end_idx])
    if p_start <= 0 or p_end <= 0:
        return np.nan
    return p_end / p_start - 1.0


def compute_residual_momentum(stock_close, market_close):
    out = {"beta": np.nan, "alpha": np.nan, "residual_momentum": np.nan,
           "ivol_annualized": np.nan, "r_squared": np.nan, "n_obs": 0}
    sr, mr = _align_returns(stock_close, market_close)
    if sr.empty:
        return out
    df = pd.concat([sr.rename("s"), mr.rename("m")], axis=1).dropna().tail(SESSIONS_12M)
    if len(df) < SESSIONS_6M:
        return out
    y = df["s"].values
    x = df["m"].values
    x_mean = x.mean()
    y_mean = y.mean()
    denom = ((x - x_mean) ** 2).sum()
    if denom <= 0:
        return out
    beta = float(((x - x_mean) * (y - y_mean)).sum() / denom)
    alpha = float(y_mean - beta * x_mean)
    residuals = y - (alpha + beta * x)
    n = len(residuals)
    ss_res = float((residuals ** 2).sum())
    ss_tot = float(((y - y_mean) ** 2).sum())
    r_squared = 1.0 - ss_res / ss_tot if ss_tot > 0 else np.nan
    ivol = float(np.std(residuals, ddof=1) * np.sqrt(252)) if n > 1 else np.nan
    resid_mom = float(np.sum(residuals[: n - SKIP_SESSIONS])) if n > SKIP_SESSIONS else np.nan
    out.update({"beta": beta, "alpha": alpha, "residual_momentum": resid_mom,
                "ivol_annualized": ivol, "r_squared": r_squared, "n_obs": n})
    return out


def compute_path_quality(close_series):
    out = {"positive_day_ratio": np.nan, "trend_r_squared": np.nan,
           "trend_slope": np.nan, "signed_r_squared": np.nan}
    s = close_series.dropna().astype(float).sort_index()
    if len(s) < FORMATION_WINDOW + SKIP_SESSIONS + 1:
        return out
    end_idx = len(s) - SKIP_SESSIONS
    start_idx = max(0, end_idx - FORMATION_WINDOW)
    window = s.iloc[start_idx:end_idx]
    if len(window) < 30:
        return out
    log_r = np.log(window / window.shift(1)).dropna()
    if len(log_r) == 0:
        return out
    out["positive_day_ratio"] = float((log_r > 0).sum() / len(log_r))
    cum_log = log_r.cumsum().values
    t = np.arange(len(cum_log))
    if len(t) >= 3:
        t_mean = t.mean()
        c_mean = cum_log.mean()
        d = ((t - t_mean) ** 2).sum()
        if d > 0:
            slope = ((t - t_mean) * (cum_log - c_mean)).sum() / d
            fitted = c_mean + slope * (t - t_mean)
            ss_res = ((cum_log - fitted) ** 2).sum()
            ss_tot = ((cum_log - c_mean) ** 2).sum()
            r2 = float(1 - ss_res / ss_tot) if ss_tot > 0 else np.nan
            out["trend_r_squared"] = r2
            out["trend_slope"] = float(slope)
            if np.isfinite(r2):
                out["signed_r_squared"] = float(r2 * np.sign(slope))
    return out


def compute_rs55(stock_close, market_close):
    """55-day relative strength vs benchmark.

    Returns dict with keys:
      ret_55d        - stock 55-session return
      nifty_ret_55d  - benchmark 55-session return
      rs55           - ret_55d - nifty_ret_55d
    All values are np.nan if either series is too short.
    """
    out = {"ret_55d": np.nan, "nifty_ret_55d": np.nan, "rs55": np.nan}
    s = stock_close.dropna().astype(float).sort_index()
    if len(s) < SESSIONS_55D + 1:
        return out
    p_now = float(s.iloc[-1])
    p_55 = float(s.iloc[-1 - SESSIONS_55D])
    if p_55 <= 0:
        return out
    out["ret_55d"] = p_now / p_55 - 1.0

    m = market_close.dropna().astype(float).sort_index() if market_close is not None else None
    if m is None or len(m) < SESSIONS_55D + 1:
        return out
    m_now = float(m.iloc[-1])
    m_55 = float(m.iloc[-1 - SESSIONS_55D])
    if m_55 <= 0:
        return out
    out["nifty_ret_55d"] = m_now / m_55 - 1.0
    out["rs55"] = out["ret_55d"] - out["nifty_ret_55d"]
    return out


def compute_ema_stack_state(close_series):
    """Four-EMA trend stack. Returns dict with EMA values and a state label.

    State values:
      STRONG_UPTREND  - price above all four EMAs, EMAs perfectly stacked
      UPTREND         - price above all four EMAs, but EMAs not perfectly stacked
      MIXED           - price inside the EMA band, or EMAs crossing
      DOWNTREND       - price below all four EMAs, EMAs not perfectly inverted
      STRONG_DOWNTREND- price below all four EMAs, EMAs perfectly inverted
      UNKNOWN         - insufficient history or missing values
    """
    out = {f"EMA_{p}": np.nan for p in EMA_PERIODS}
    out["EMA_Stack_State"] = "UNKNOWN"
    s = close_series.dropna().astype(float).sort_index()
    if len(s) < max(EMA_PERIODS) + 1:
        return out
    for p in EMA_PERIODS:
        out[f"EMA_{p}"] = float(s.ewm(span=p, adjust=False).mean().iloc[-1])

    price = float(s.iloc[-1])
    e21, e55, e100, e200 = (
        out["EMA_21"], out["EMA_55"], out["EMA_100"], out["EMA_200"]
    )
    if any(not np.isfinite(v) for v in (e21, e55, e100, e200)):
        return out

    above_all = price > max(e21, e55, e100, e200)
    below_all = price < min(e21, e55, e100, e200)
    stacked = e21 > e55 > e100 > e200
    inverted = e21 < e55 < e100 < e200

    if above_all and stacked:
        out["EMA_Stack_State"] = "STRONG_UPTREND"
    elif above_all:
        out["EMA_Stack_State"] = "UPTREND"
    elif below_all and inverted:
        out["EMA_Stack_State"] = "STRONG_DOWNTREND"
    elif below_all:
        out["EMA_Stack_State"] = "DOWNTREND"
    else:
        out["EMA_Stack_State"] = "MIXED"
    return out


def compute_universe_crowding(returns_df, lookback=60):
    if returns_df is None or returns_df.empty:
        return pd.Series(dtype=float)
    window = returns_df.tail(lookback).dropna(axis=1, how="all")
    if window.shape[1] < 3:
        return pd.Series(dtype=float)
    corr = window.corr(min_periods=20)
    out = {}
    for col in corr.columns:
        vals = corr[col].drop(index=col, errors="ignore").values
        vals = vals[np.isfinite(vals)]
        out[col] = float(np.mean(vals)) if len(vals) > 0 else np.nan
    return pd.Series(out, dtype=float)


def compute_volatility_multiplier(market_close):
    out = {"realized_vol_60d": np.nan, "realized_vol_252d": np.nan,
           "blended_vol": np.nan, "regime": "UNKNOWN", "multiplier": MULT_UNKNOWN}
    mr = _log_returns(market_close)
    if len(mr) < 60:
        return out
    v60 = float(mr.tail(60).std(ddof=1) * np.sqrt(252))
    v252 = float(mr.tail(252).std(ddof=1) * np.sqrt(252)) if len(mr) >= 252 else v60
    blended = 0.6 * v60 + 0.4 * v252
    if blended < VOL_LOW:
        regime, mult = "LOW_VOL", MULT_FULL
    elif blended < VOL_MODERATE:
        regime, mult = "MODERATE", MULT_MODERATE
    elif blended < VOL_HIGH:
        regime, mult = "HIGH_VOL", MULT_DEFENSIVE
    else:
        regime, mult = "CRISIS", MULT_FLAT
    out.update({"realized_vol_60d": v60, "realized_vol_252d": v252,
                "blended_vol": blended, "regime": regime, "multiplier": mult})
    return out


def compute_institutional_momentum_scores(df, close_df, market_close):
    if df is None or df.empty:
        return df
    stock_returns = np.log(close_df / close_df.shift(1)).dropna(how="all")
    crowding = compute_universe_crowding(stock_returns, lookback=60)
    rows = []
    for ticker in df["Ticker"].astype(str):
        yf = f"{ticker}.NS"
        s_close = close_df.get(yf)
        if s_close is None:
            s_close = close_df.get(ticker)
        r = {"Ticker": ticker, "Ret_12_1M": np.nan, "Beta_252": np.nan,
             "Residual_Mom_12_1": np.nan, "IVOL_Annualized": np.nan,
             "Path_Positive_Ratio": np.nan, "Path_Trend_R2": np.nan,
             "Path_Signed_R2": np.nan, "Crowding_Stock": np.nan,
             "Ret_55D": np.nan, "Nifty_Ret_55D": np.nan, "RS55": np.nan,
             "EMA_21": np.nan, "EMA_55": np.nan, "EMA_100": np.nan,
             "EMA_200": np.nan, "EMA_Stack_State": "UNKNOWN"}
        if s_close is not None and not s_close.dropna().empty:
            r["Ret_12_1M"] = compute_12_1_momentum(s_close)
            resid = compute_residual_momentum(s_close, market_close)
            r["Beta_252"] = resid["beta"]
            r["Residual_Mom_12_1"] = resid["residual_momentum"]
            r["IVOL_Annualized"] = resid["ivol_annualized"]
            path = compute_path_quality(s_close)
            r["Path_Positive_Ratio"] = path["positive_day_ratio"]
            r["Path_Trend_R2"] = path["trend_r_squared"]
            r["Path_Signed_R2"] = path["signed_r_squared"]
            r["Crowding_Stock"] = float(crowding.get(yf, crowding.get(ticker, np.nan)))
            rs55_result = compute_rs55(s_close, market_close)
            r["Ret_55D"] = rs55_result["ret_55d"]
            r["Nifty_Ret_55D"] = rs55_result["nifty_ret_55d"]
            r["RS55"] = rs55_result["rs55"]
            ema_result = compute_ema_stack_state(s_close)
            for p in EMA_PERIODS:
                r[f"EMA_{p}"] = ema_result[f"EMA_{p}"]
            r["EMA_Stack_State"] = ema_result["EMA_Stack_State"]
        rows.append(r)
    v2 = pd.DataFrame(rows)
    df = df.merge(v2, on="Ticker", how="left")
    rankable = df["Data_Quality"].astype(str).isin(["PASS", "REVIEW"]) & df["Ret_6M"].notna()
    df["Z_Ret_12_1"] = _zscore(df["Ret_12_1M"], rankable)
    df["Z_Residual"] = _zscore(df["Residual_Mom_12_1"], rankable)
    df["Z_Path"] = _zscore(df["Path_Signed_R2"], rankable)
    df["Z_IVOL"] = _zscore(df["IVOL_Annualized"], rankable)
    df["Z_Crowding"] = _zscore(df["Crowding_Stock"], rankable)
    df["Inst_Composite_Z"] = (
        W_12_1 * df["Z_Ret_12_1"]
        + W_RESIDUAL * df["Z_Residual"]
        + W_PATH * df["Z_Path"]
        + W_IVOL_PENALTY * df["Z_IVOL"]
        + W_CROWDING_PENALTY * df["Z_Crowding"]
    )
    mask = df["Inst_Composite_Z"].notna()
    df["Inst_Percentile"] = np.nan
    df.loc[mask, "Inst_Percentile"] = (
        df.loc[mask, "Inst_Composite_Z"].rank(method="average", pct=True) * 100.0
    )
    df["Inst_Rank"] = np.nan
    df.loc[mask, "Inst_Rank"] = (
        df.loc[mask, "Inst_Composite_Z"].rank(method="min", ascending=False)
    )
    # Trusted watchlist rank: PASS rows only (REVIEW rows stay quarantined).
    pass_mask = mask & (df["Data_Quality"].astype(str) == "PASS")
    df["Inst_Rank_PASS"] = np.nan
    df.loc[pass_mask, "Inst_Rank_PASS"] = (
        df.loc[pass_mask, "Inst_Composite_Z"].rank(method="min", ascending=False)
    )
    return df


def last_friday_of_month(d):
    d = pd.Timestamp(d).date()
    if d.month == 12:
        first_next = pd.Timestamp(d.year + 1, 1, 1).date()
    else:
        first_next = pd.Timestamp(d.year, d.month + 1, 1).date()
    last = first_next - pd.Timedelta(days=1).to_pytimedelta()
    while last.weekday() != 4:
        last = last - pd.Timedelta(days=1).to_pytimedelta()
    return last


def is_month_end_anchor(weekly_key):
    try:
        d = pd.Timestamp(weekly_key).date()
    except Exception:
        return False
    if d.weekday() != 4:
        return False
    return d == last_friday_of_month(d)
