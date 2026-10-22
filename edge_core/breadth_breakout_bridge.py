"""Research-only breakout outcome comparison against contemporaneous breadth.

The breadth series is calculated from the available current universe and has
survivorship bias. It is not a point-in-time index-membership backtest.
"""
import pandas as pd


def breadth_breakout_summary(events, breadth, *, low_threshold=40, high_threshold=60):
    if not {"Session", "Outcome"}.issubset(events.columns):
        raise ValueError("Missing breakout outcome fields")
    if not {"Above_50_Pct", "Above_200_Pct"}.issubset(breadth.columns):
        raise ValueError("Missing breadth fields")
    if not breadth.index.is_monotonic_increasing or breadth.index.has_duplicates:
        raise ValueError("Breadth sessions must be sorted and unique")
    frame = events.copy()
    frame["Session"] = pd.to_datetime(frame["Session"], errors="raise").dt.normalize()
    snapshot = breadth[["Above_50_Pct", "Above_200_Pct"]].copy()
    snapshot.index = pd.to_datetime(snapshot.index).normalize()
    if snapshot.index.has_duplicates:
        raise ValueError("Duplicate breadth sessions")
    frame = frame.join(snapshot, on="Session")
    a, b = frame["Above_50_Pct"], frame["Above_200_Pct"]
    frame["Breadth_Group"] = "NO_BREADTH"
    valid = a.notna() & b.notna()
    frame.loc[valid, "Breadth_Group"] = "MIXED"
    frame.loc[valid & ((a < low_threshold) | (b < low_threshold)), "Breadth_Group"] = "DEFENSIVE"
    frame.loc[valid & (a >= high_threshold) & (b >= high_threshold), "Breadth_Group"] = "BROAD"
    rows = []
    for group in ("BROAD", "MIXED", "DEFENSIVE", "NO_BREADTH"):
        subset = frame[frame["Breadth_Group"] == group]
        wins = int((subset["Outcome"] == "SUCCESS").sum())
        losses = int(subset["Outcome"].isin(["FAILURE", "STOP_BREACH"]).sum())
        resolved = wins + losses
        rows.append({"Breadth_At_Breakout": group, "Qualified": len(subset),
                     "Resolved": resolved, "Successes": wins,
                     "Failures_Incl_Stops": losses,
                     "Unresolved": len(subset)-resolved,
                     "Success_Rate_Pct": round(100*wins/resolved, 1) if resolved else None})
    return pd.DataFrame(rows)
