"""Generate conservative evidence candidates from the actual Leadership Scanner output.

Only the frozen Momentum V1 scoring function may produce ranking input.
This adapter selects research rows for manual evidence review; it never
certifies a stock or changes any momentum scores.
"""
import pandas as pd


def evidence_shortlist(scored, membership, *, percentile_floor=80):
    required = {"Symbol", "Percentile", "Data_Quality"}
    if not required.issubset(scored.columns):
        raise ValueError("Missing scored leadership columns")
    if not {"Symbol", "ISIN Code"}.issubset(membership.columns):
        raise ValueError("Missing official membership columns")
    identities = membership[["Symbol", "ISIN Code"]].copy()
    identities["Symbol"] = identities["Symbol"].astype(str).str.strip().str.upper()
    identities["ISIN Code"] = identities["ISIN Code"].astype(str).str.strip().str.upper()
    if (identities["Symbol"].duplicated().any() or identities["ISIN Code"].duplicated().any()
        or identities["Symbol"].eq("").any() or identities["ISIN Code"].eq("").any()):
        raise ValueError("Official membership identities must be complete and unique")
    ranked = scored.copy()
    ranked["Symbol"] = ranked["Symbol"].astype(str).str.strip().str.upper()
    if ranked["Symbol"].duplicated().any():
        raise ValueError("Duplicate ranked symbols")
    chosen = ranked.loc[
        pd.to_numeric(ranked["Percentile"], errors="coerce").ge(percentile_floor)
        & ranked["Data_Quality"].isin(["PASS", "REVIEW"]), ["Symbol", "Percentile", "Data_Quality"]
    ]
    joined = chosen.merge(identities, on="Symbol", how="left", validate="one_to_one")
    if joined["ISIN Code"].isna().any():
        raise ValueError("Research shortlist missing official ISIN identity")
    return [
        {"symbol": row["Symbol"], "isin": row["ISIN Code"],
         "research_percentile": float(row["Percentile"]),
         "technical_data_quality": row["Data_Quality"],
         "certified": False}
        for _, row in joined.sort_values(["Percentile", "Symbol"], ascending=[False, True]).iterrows()
    ]
