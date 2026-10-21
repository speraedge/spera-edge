"""Independent, conservative diagnostics. No trading signals."""
import pandas as pd

def stage2_template(close):
    s = pd.to_numeric(close, errors="coerce").dropna()
    if len(s) < 252 or (s <= 0).any():
        return {"eligible": False, "reason": "Insufficient valid price history"}
    ma50 = s.rolling(50).mean()
    ma150 = s.rolling(150).mean()
    ma200 = s.rolling(200).mean()
    price = float(s.iloc[-1])
    low = float(s.tail(252).min())
    high = float(s.tail(252).max())
    checks = {
        "Price > 150/200 DMA": price > ma150.iloc[-1] and price > ma200.iloc[-1],
        "150 DMA > 200 DMA": ma150.iloc[-1] > ma200.iloc[-1],
        "200 DMA rising over 20 sessions": ma200.iloc[-1] > ma200.iloc[-21],
        "50 DMA > 150/200 DMA": ma50.iloc[-1] > ma150.iloc[-1] and ma50.iloc[-1] > ma200.iloc[-1],
        "Price > 50 DMA": price > ma50.iloc[-1],
        "At least 30% above 52-week low": price >= 1.30 * low,
        "Within 25% of 52-week high": price >= 0.75 * high,
    }
    return {"eligible": all(checks.values()), "checks": checks, "reason": "Price-only template; relative strength is a separate gate"}

def market_breadth(close_df):
    if close_df is None or close_df.empty:
        return {"coverage": 0, "above_50_pct": None, "above_200_pct": None}
    n50 = n200 = eligible50 = eligible200 = 0
    for col in close_df:
        s = pd.to_numeric(close_df[col], errors="coerce").dropna()
        if len(s) >= 50:
            eligible50 += 1
            n50 += bool(s.iloc[-1] > s.tail(50).mean())
        if len(s) >= 200:
            eligible200 += 1
            n200 += bool(s.iloc[-1] > s.tail(200).mean())
    return {"coverage": len(close_df.columns), "eligible_50": eligible50, "eligible_200": eligible200, "above_50_pct": round(100*n50/eligible50, 1) if eligible50 else None, "above_200_pct": round(100*n200/eligible200, 1) if eligible200 else None}
