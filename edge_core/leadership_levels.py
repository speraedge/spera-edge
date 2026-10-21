"""Three-level research classification. Never converts REVIEW into a trading signal."""
import pandas as pd
from edge_core.analytics import stage2_template

def classify_leadership(ranks, close, setups=None, min_percentile=80):
    """Return ranked research with price-template and setup diagnostics.

    Missing benchmark-relative-strength, corporate-action certification and
    sector evidence keep the SEPA and actionable gates explicitly pending.
    """
    if ranks is None or "Symbol" not in ranks or "Data_Quality" not in ranks:
        raise ValueError("Leadership research must contain Symbol and Data_Quality")
    out = ranks.copy()
    if out["Symbol"].isna().any() or out["Symbol"].duplicated().any():
        raise ValueError("Leadership symbol identities invalid")
    out["Momentum_Leader"] = (
        out["Data_Quality"].eq("PASS")
        & pd.to_numeric(out.get("Percentile", pd.Series(index=out.index, dtype=float)), errors="coerce").ge(min_percentile)
    )
    stage = {}
    if close is not None:
        for symbol in out["Symbol"]:
            if symbol in close.columns:
                stage[symbol] = stage2_template(close[symbol])["eligible"]
    out["Provisional_Momentum_Candidate"] = (out["Data_Quality"].eq("REVIEW") & pd.to_numeric(out.get("Percentile", pd.Series(index=out.index, dtype=float)), errors="coerce").ge(min_percentile))
    out["Price_Template_Pass"] = out["Symbol"].map(stage).fillna(False).astype(bool)
    setup_symbols = set()
    if setups is not None and not setups.empty and "Ticker" in setups:
        setup_symbols = set(setups["Ticker"].dropna().astype(str))
    out["Setup_Diagnostic"] = out["Symbol"].isin(setup_symbols)
    # Technical diagnostics only: a cross-sectional percentile is not a verified
    # benchmark RS series, and no audited earnings/source evidence is available.
    out["SEPA_Technical_Research"] = False
    out["SEPA_Certified"] = False
    out["SEPA_Status"] = "PENDING_RS_SECTOR_AND_SOURCE_VERIFICATION"
    out["Setup_Status"] = "NOT_CERTIFIED"
    out["Research_Level"] = "UNQUALIFIED"
    out.loc[out["Provisional_Momentum_Candidate"], "Research_Level"] = "PROVISIONAL_MOMENTUM"
    out.loc[out["Momentum_Leader"], "Research_Level"] = "MOMENTUM_LEADER"
    out.loc[out["Provisional_Momentum_Candidate"] & out["Price_Template_Pass"], "Research_Level"] = "PROVISIONAL_PRICE_TEMPLATE_PASS"
    out.loc[out["Momentum_Leader"] & out["Price_Template_Pass"], "Research_Level"] = "PRICE_TEMPLATE_PASS"
    out.loc[out["Provisional_Momentum_Candidate"] & out["Price_Template_Pass"] & out["Setup_Diagnostic"], "Research_Level"] = "PROVISIONAL_SETUP_REVIEW"
    out.loc[out["Momentum_Leader"] & out["Price_Template_Pass"] & out["Setup_Diagnostic"], "Research_Level"] = "SETUP_REVIEW"
    return out
