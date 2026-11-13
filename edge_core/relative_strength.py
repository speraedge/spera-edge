"""Benchmark-relative strength from aligned daily closes; research only."""
import numpy as np
import pandas as pd

def relative_strength(stock_close, benchmark_close, lookbacks=(63,126,252)):
    stock=pd.to_numeric(stock_close,errors="coerce")
    benchmark=pd.to_numeric(benchmark_close,errors="coerce")
    aligned=pd.concat([stock.rename("stock"),benchmark.rename("benchmark")],axis=1).dropna().sort_index()
    if aligned.index.has_duplicates or (aligned<=0).any().any():
        raise ValueError("Invalid or duplicated
