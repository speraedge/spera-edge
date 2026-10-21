"""risk_engine.py - portfolio-level risk layer. Pure functions: no I/O, no Streamlit.

It consumes ranks; it NEVER changes V1 or V2 ranks (handover note, Section 7).

Multiplier precedence (single definition, used everywhere):

    exposure_mult = min(1.0, regime_mult x drawdown_mult x vol_scaler)

  * regime_mult   : 1.0 / 0.7 / 0.4 / 0.0 from the market regime (0.7 if UNKNOWN).
  * drawdown_mult : 1.0 normally, 0.5 at >=10% drawdown, 0.0 at >=15% (no new entries).
  * vol_scaler    : target_vol / realized momentum-portfolio vol, clipped to
                    [scaler_min, scaler_max]. scaler_max defaults to 1.0 so the
                    scaler can only cut exposure and can never undo a regime cut.
The overall product is capped at 1.0 (no leverage).

Heat = sum over open positions of (entry - stop) x qty / capital. A hard cap applies
AFTER exposure scaling, so heat is the last line of defence.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class RiskConfig:
    risk_per_trade_pct: float = 1.0      # matches the existing Risk Engine slider default
    heat_cap_pct: float = 6.0            # ONE number (the old note said "4-6%")
    default_stop_pct: float = 0.15       # used only when a position has no stop (flagged ASSUMED)
    dd_halve: float = 0.10
    dd_stop: float = 0.15
    max_per_sector: int = 3
    max_single_weight: float = 0.08
    target_vol: float = 0.15
    scaler_min: float = 0.25
    scaler_max: float = 1.0
    min_weeks_for_scaler: int = 12
    adtv_pass_cr: float = 10.0
    adtv_caution_cr: float = 2.0
    unknown_regime_mult: float = 0.7
    # Round-trip cost ESTIMATES (assumptions - replace with your contract note).
    base_round_trip_cost_pct: float = 0.40
    slippage_pass_pct: float = 0.10
    slippage_caution_pct: float = 0.50


DEFAULT_CONFIG = RiskConfig()


# ---------------------------------------------------------------- liquidity
def liquidity_flag(adtv_cr: float, cfg: RiskConfig = DEFAULT_CONFIG) -> str:
    """PASS >= 10 Cr, CAUTION 2-10 Cr, FAIL < 2 Cr, UNKNOWN if missing."""
    if adtv_cr is None or not np.isfinite(adtv_cr):
        return "UNKNOWN"
    if adtv_cr >= cfg.adtv_pass_cr:
        return "PASS"
    if adtv_cr >= cfg.adtv_caution_cr:
        return "CAUTION"
    return "FAIL"


def round_trip_cost_pct(flag: str, cfg: RiskConfig = DEFAULT_CONFIG) -> float:
    """Estimated round-trip cost incl. slippage, in percent. FAIL/UNKNOWN -> NaN."""
    if flag == "PASS":
        return cfg.base_round_trip_cost_pct + cfg.slippage_pass_pct
    if flag == "CAUTION":
        return cfg.base_round_trip_cost_pct + cfg.slippage_caution_pct
    return float("nan")


# ------------------------------------------------------------------ regime
def regime_multiplier(regime: Optional[dict], cfg: RiskConfig = DEFAULT_CONFIG) -> float:
    if not isinstance(regime, dict) or str(regime.get("regime", "UNKNOWN")) == "UNKNOWN":
        return cfg.unknown_regime_mult
    try:
        m = float(regime.get("multiplier", cfg.unknown_regime_mult))
    except (TypeError, ValueError):
        return cfg.unknown_regime_mult
    return m if np.isfinite(m) else cfg.unknown_regime_mult


# ---------------------------------------------------------------- drawdown
def drawdown_state(equity: pd.Series, cfg: RiskConfig = DEFAULT_CONFIG) -> Dict:
    """Current drawdown from the running peak of the user's own equity log."""
    eq = pd.to_numeric(equity, errors="coerce").dropna() if equity is not None else pd.Series(dtype=float)
    if len(eq) and ((~np.isfinite(eq)).any() or (eq <= 0).any()):
        return {"drawdown": float("nan"), "state": "INVALID_EQUITY", "size_mult": 0.0,
                "allow_new_entries": False,
                "error": "Equity history must contain only finite values greater than zero."}
    if len(eq) < 2:
        return {"drawdown": float("nan"), "state": "NO_DATA", "size_mult": 1.0,
                "allow_new_entries": True}
    dd = float(1.0 - eq.iloc[-1] / eq.cummax().iloc[-1])
    if dd >= cfg.dd_stop:
        state, mult, allow = "STOP_NEW_ENTRIES", 0.0, False
    elif dd >= cfg.dd_halve:
        state, mult, allow = "HALVE_SIZE", 0.5, True
    else:
        state, mult, allow = "NORMAL", 1.0, True
    return {"drawdown": dd, "state": state, "size_mult": mult, "allow_new_entries": allow}


# ------------------------------------------------------------- vol scaler
def vol_scaler(weekly_returns: pd.Series, cfg: RiskConfig = DEFAULT_CONFIG) -> Dict:
    """target_vol / realized vol of the user's own weekly equity returns.

    Needs >= cfg.min_weeks_for_scaler observations; std of 4 weekly points (the old
    spec) is far too noisy. Below that the scaler is neutral (1.0) and flagged.
    """
    r = pd.to_numeric(weekly_returns, errors="coerce").dropna() if weekly_returns is not None else pd.Series(dtype=float)
    if len(r) < cfg.min_weeks_for_scaler:
        return {"scaler": 1.0, "realized_vol": float("nan"), "status": "INSUFFICIENT_HISTORY",
                "n_weeks": int(len(r))}
    rv = float(r.tail(26).std(ddof=1) * np.sqrt(52))
    if not np.isfinite(rv) or rv <= 0:
        return {"scaler": 1.0, "realized_vol": rv, "status": "INVALID_VOL", "n_weeks": int(len(r))}
    s = float(np.clip(cfg.target_vol / rv, cfg.scaler_min, cfg.scaler_max))
    return {"scaler": s, "realized_vol": rv, "status": "OK", "n_weeks": int(len(r))}


def combine_multipliers(regime_mult: float, dd_mult: float, scaler: float,
                        cfg: RiskConfig = DEFAULT_CONFIG) -> float:
    return float(min(1.0, max(0.0, regime_mult) * max(0.0, dd_mult) * max(0.0, scaler)))


# -------------------------------------------------------------------- heat
def portfolio_heat(positions: pd.DataFrame, capital: float,
                   cfg: RiskConfig = DEFAULT_CONFIG) -> Dict:
    """positions columns: ticker, qty, entry_price, stop_price (may be NaN)."""
    empty = {"heat_pct": 0.0, "rows": pd.DataFrame(), "assumed_stop_count": 0,
             "remaining_pct": cfg.heat_cap_pct, "breached": False,
             "status": "OK", "error": ""}
    try:
        capital = float(capital)
    except (TypeError, ValueError):
        capital = float("nan")
    if not np.isfinite(capital) or capital <= 0:
        return {**empty, "heat_pct": float("nan"), "status": "INVALID_INPUT",
                "error": "Capital must be a finite value greater than zero."}
    if positions is None or positions.empty:
        return empty
    p = positions.copy()
    required = {"qty", "entry_price", "stop_price"}
    missing = required.difference(p.columns)
    if missing:
        return {**empty, "heat_pct": float("nan"), "status": "INVALID_INPUT",
                "error": "Missing position columns: " + ", ".join(sorted(missing))}
    active = p[list(required)].notna().any(axis=1)
    if "ticker" in p.columns:
        active |= p["ticker"].fillna("").astype(str).str.strip().ne("")
    p = p.loc[active].copy()
    if p.empty:
        return empty
    for c in ("qty", "entry_price", "stop_price"):
        p[c] = pd.to_numeric(p[c], errors="coerce")
    invalid_qty = p["qty"].isna() | ~np.isfinite(p["qty"]) | (p["qty"] < 0)
    invalid_entry = p["entry_price"].isna() | ~np.isfinite(p["entry_price"]) | (p["entry_price"] <= 0)
    if invalid_qty.any() or invalid_entry.any():
        reasons = []
        if invalid_qty.any():
            reasons.append("quantity must be finite, present, and non-negative")
        if invalid_entry.any():
            reasons.append("entry price must be finite and greater than zero")
        return {**empty, "heat_pct": float("nan"), "status": "INVALID_INPUT",
                "error": "; ".join(reasons), "rows": p}
    assumed = (
        p["stop_price"].isna()
        | (p["stop_price"] <= 0)
        | (p["stop_price"] >= p["entry_price"])
    )
    stop = p["stop_price"].where(~assumed, p["entry_price"] * (1.0 - cfg.default_stop_pct))
    p["risk_rupees"] = (p["entry_price"] - stop).clip(lower=0) * p["qty"]
    p["risk_pct"] = p["risk_rupees"] / capital * 100.0
    p["stop_assumed"] = assumed
    heat = float(p["risk_pct"].sum())
    return {"heat_pct": heat, "rows": p, "assumed_stop_count": int(assumed.sum()),
            "remaining_pct": max(cfg.heat_cap_pct - heat, 0.0),
            "breached": heat > cfg.heat_cap_pct, "status": "OK", "error": ""}


# ------------------------------------------------------- selection/weights
def select_with_sector_cap(ranked: pd.DataFrame, n: int, rank_col: str,
                           sector_col: str = "Sector",
                           max_per_sector: int = DEFAULT_CONFIG.max_per_sector) -> pd.DataFrame:
    """Walk down the ranking, skipping names once a sector has `max_per_sector`."""
    if ranked is None or ranked.empty:
        return pd.DataFrame()
    r = ranked.sort_values([rank_col, "Ticker"]).reset_index(drop=True)
    picked, counts = [], {}
    for i, row in r.iterrows():
        sec = row.get(sector_col, "Unknown")
        if counts.get(sec, 0) >= max_per_sector:
            continue
        picked.append(i)
        counts[sec] = counts.get(sec, 0) + 1
        if len(picked) >= n:
            break
    return r.loc[picked].reset_index(drop=True)


def inverse_vol_weights(ann_vol: pd.Series, max_weight: Optional[float] = None) -> pd.Series:
    """weight_i = (1/vol_i) / sum(1/vol_j), optionally capped with redistribution.

    A cap that is infeasible (max_weight * n < 1) is ignored rather than looping.
    """
    v = pd.to_numeric(ann_vol, errors="coerce")
    inv = 1.0 / v.where(v > 0)
    if inv.notna().sum() == 0:
        return pd.Series(np.nan, index=ann_vol.index)
    w = inv / inv.sum()
    if max_weight is None or max_weight * w.notna().sum() < 1.0 - 1e-12:
        return w
    for _ in range(50):
        over = w > max_weight + 1e-12
        if not over.any():
            break
        excess = float((w[over] - max_weight).sum())
        w[over] = max_weight
        room = ~over & w.notna()
        if not room.any():
            break
        w[room] += excess * w[room] / w[room].sum()
    return w


def size_position(capital: float, entry: float, stop: float, exposure_mult: float,
                  remaining_heat_pct: float, cfg: RiskConfig = DEFAULT_CONFIG) -> Dict:
    """Fixed-fractional shares, scaled by exposure, then trimmed to the heat headroom."""
    try:
        capital, entry, stop = float(capital), float(entry), float(stop)
        exposure_mult = float(exposure_mult)
        remaining_heat_pct = float(remaining_heat_pct)
    except (TypeError, ValueError):
        return {"qty": 0, "risk_pct": 0.0, "blocked": "INVALID_INPUT"}
    if (not all(np.isfinite(v) for v in
                (capital, entry, stop, exposure_mult, remaining_heat_pct))
            or capital <= 0 or entry <= 0 or stop <= 0 or stop >= entry
            or exposure_mult < 0 or exposure_mult > 1
            or remaining_heat_pct < 0):
        return {"qty": 0, "risk_pct": 0.0, "blocked": "INVALID_INPUT"}
    if exposure_mult <= 0:
        return {"qty": 0, "risk_pct": 0.0, "blocked": "EXPOSURE_ZERO"}
    per_share = entry - stop
    risk_pct = min(cfg.risk_per_trade_pct * exposure_mult, remaining_heat_pct)
    if risk_pct <= 0:
        return {"qty": 0, "risk_pct": 0.0, "blocked": "HEAT_CAP"}
    qty = int((capital * risk_pct / 100.0) // per_share)
    return {"qty": qty, "risk_pct": qty * per_share / capital * 100.0,
            "blocked": "" if qty > 0 else "TOO_SMALL"}


def build_target_portfolio(candidates: pd.DataFrame, capital: float, exposure_mult: float,
                           n: int = 25, rank_col: str = "Inst_Rank",
                           cfg: RiskConfig = DEFAULT_CONFIG) -> pd.DataFrame:
    """Sector-capped top-n, inverse-vol weights, scaled by exposure_mult.

    Candidates should be PASS-only rows with columns Ticker, Sector, AnnVol,
    Price, ADTV_Cr and `rank_col`. Invalid ranks/volatility/prices and unknown
    liquidity are excluded; FAIL liquidity remains ineligible.
    """
    try:
        capital, exposure_mult = float(capital), float(exposure_mult)
        n = int(n)
    except (TypeError, ValueError):
        raise ValueError("capital, exposure multiplier, and basket size must be numeric")
    if not np.isfinite(capital) or capital <= 0:
        raise ValueError("capital must be finite and greater than zero")
    if not np.isfinite(exposure_mult) or not 0.0 <= exposure_mult <= 1.0:
        raise ValueError("exposure multiplier must be between zero and one")
    if n <= 0:
        raise ValueError("basket size must be greater than zero")
    required = {"Ticker", "Sector", "AnnVol", "Price", "ADTV_Cr", rank_col}
    missing = required.difference(candidates.columns if candidates is not None else ())
    if missing:
        raise ValueError("target portfolio missing columns: " + ", ".join(sorted(missing)))
    prepared = candidates.copy()
    prepared["Sector"] = (
        prepared["Sector"].fillna("Unknown").astype(str).str.strip()
        .replace("", "Unknown")
    )
    for column in ("AnnVol", "Price", "ADTV_Cr", rank_col):
        prepared[column] = pd.to_numeric(prepared[column], errors="coerce")
    valid = (
        np.isfinite(prepared[rank_col])
        & np.isfinite(prepared["AnnVol"])
        & (prepared["AnnVol"] > 0)
        & np.isfinite(prepared["Price"])
        & (prepared["Price"] > 0)
    )
    prepared = prepared.loc[valid].copy()
    prepared["Liquidity"] = prepared["ADTV_Cr"].apply(lambda x: liquidity_flag(x, cfg))
    prepared = prepared[prepared["Liquidity"].isin(("PASS", "CAUTION"))]
    sel = select_with_sector_cap(prepared, n, rank_col, "Sector", cfg.max_per_sector)
    if sel.empty:
        return sel
    w = inverse_vol_weights(sel["AnnVol"], cfg.max_single_weight)
    sel["Base_Weight"] = w
    sel["Target_Weight"] = w * exposure_mult
    sel["Target_Value"] = sel["Target_Weight"] * capital
    sel["Target_Shares"] = np.floor(sel["Target_Value"] / sel["Price"]).astype("Int64")
    sel["Est_Round_Trip_Cost_Pct"] = sel["Liquidity"].apply(lambda f: round_trip_cost_pct(f, cfg))
    return sel
