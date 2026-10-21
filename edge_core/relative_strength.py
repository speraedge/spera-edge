"""Benchmark-relative strength from aligned daily closes; research only."""
import numpy as np
import pandas as pd

def relative_strength(stock_close, benchmark_close, lookbacks=(63,126,252)):
    stock=pd.to_numeric(stock_close,errors="coerce")
    benchmark=pd.to_numeric(benchmark_close,errors="coerce")
    aligned=pd.concat([stock.rename("stock"),benchmark.rename("benchmark")],axis=1).dropna().sort_index()
    if aligned.index.has_duplicates or (aligned<=0).any().any():
        raise ValueError("Invalid or duplicated benchmark/stock sessions")
    result={}
    for n in lookbacks:
        if len(aligned)<=n:
            result[f"RS_{n}D"]=np.nan
            continue
        a=aligned.iloc[-1]
        b=aligned.iloc[-n-1]
        result[f"RS_{n}D"]=float(a["stock"]/b["stock"]-a["benchmark"]/b["benchmark"])
    result["RS_Evidence"]="COMPUTED_ALIGNED" if all(np.isfinite(v) for v in result.values()) else "INSUFFICIENT_HISTORY"
    return result

def cross_sectional_rs(close, lookbacks=(63,126,252)):
    """Price-performance percentile within the available stock universe.

    This is NOT benchmark-relative RS or Minervini's proprietary RS rating.
    Each horizon ranks only symbols with positive, finite, complete endpoints.
    """
    if close is None or close.empty or close.index.has_duplicates or close.columns.has_duplicates:
        raise ValueError("Unique nonempty OHLCV close matrix required")
    if not close.index.is_monotonic_increasing:
        raise ValueError("Sessions must be sorted")
    prices=close.apply(pd.to_numeric,errors="coerce")
    result=pd.DataFrame({"Symbol":prices.columns})
    for days in lookbacks:
        key=f"RS_Universe_{days}D_Pctile"
        if len(prices)<=days:
            result[key]=float("nan")
            continue
        now=prices.iloc[-1]
        then=prices.iloc[-days-1]
        returns=(now/then-1).where((now>0)&(then>0))
        returns=returns.replace([np.inf,-np.inf],np.nan)
        result[key]=result["Symbol"].map((returns.rank(pct=True)*100).to_dict())
    result["RS_Method"]="NIFTY_500_CROSS_SECTIONAL_PRICE_PERCENTILE_NOT_BENCHMARK"
    return result
