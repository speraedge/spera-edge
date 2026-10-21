"""Current price momentum grouped by dated, incomplete historical sector membership."""
import pandas as pd
import numpy as np

def current_sector_research(close, cohorts, mapping_week, lookback=63):
    if close is None or close.empty or len(close)<=lookback:
        raise ValueError("Insufficient price history for sector research")
    if not {"ticker","sector","week_key"}.issubset(cohorts.columns):
        raise ValueError("Sector membership evidence missing")
    if not cohorts["week_key"].eq(mapping_week).all() or cohorts["ticker"].duplicated().any():
        raise ValueError("Sector membership dates or identities invalid")
    if close.columns.has_duplicates or close.index.has_duplicates:
        raise ValueError("Duplicate market data identities")
    end=pd.to_numeric(close.iloc[-1],errors="coerce")
    start=pd.to_numeric(close.iloc[-lookback-1],errors="coerce")
    returns=((end/start)-1).where((start>0)&(end>0)).replace([np.inf,-np.inf],np.nan)
    members=cohorts[["ticker","sector"]].rename(columns={"ticker":"Symbol","sector":"Sector"})
    members["Return"]=members["Symbol"].map(returns.to_dict())
    groups=members.groupby("Sector",dropna=True).agg(
        Mapped_Stocks=("Symbol","size"),
        Stocks_With_Price=("Return","count"),
        Median_Return=("Return","median"),
        Mean_Return=("Return","mean"),
        Positive_Stocks=("Return",lambda x:int((x>0).sum()))
    ).reset_index()
    groups["Breadth_Positive_Pct"]=100*groups["Positive_Stocks"]/groups["Stocks_With_Price"].replace(0,np.nan)
    groups["Current_Sector_Rank"]=groups["Median_Return"].rank(method="min",ascending=False)
    groups["Mapping_As_Of"]=mapping_week
    groups["Sector_Trust"]="PROVISIONAL_HISTORICAL_MEMBERSHIP"
    return groups.sort_values(["Current_Sector_Rank","Sector"],na_position="last").reset_index(drop=True)
