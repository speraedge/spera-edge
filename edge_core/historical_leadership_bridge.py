"""Join independently dated EDGE breakout events to read-only Wisdom weekly ranks.

Historical snapshots are reference observations, never certified EDGE signals.
Only observations strictly earlier than the breakout session are eligible.
"""
import hashlib
import json
from pathlib import Path

import pandas as pd


def historical_leadership_context(events, directory):
    root = Path(directory)
    manifest = json.loads((root / "manifest.json").read_text())
    if manifest.get("universe") != "NIFTY_500":
        raise ValueError("Wrong historical universe")
    observations = []
    for item in manifest["weeks"]:
        key = str(item["weekly_key"])
        date = pd.Timestamp(key)
        path = root / str(item["file"])
        if path.parent.resolve() != root.resolve():
            raise ValueError("Unsafe history path")
        raw = path.read_bytes()
        if hashlib.sha256(raw).hexdigest() != item["sha256"]:
            raise ValueError("Historical checksum mismatch")
        frame = pd.read_csv(path)
        if len(frame) != int(item["rows"]) or not {"Ticker", "Pure_Momentum_Rank", "Data_Quality"}.issubset(frame):
            raise ValueError("Invalid historical leadership schema")
        if frame["Ticker"].duplicated().any():
            raise ValueError("Duplicate historical symbols")
        for _, row in frame.iterrows():
            observations.append({"Symbol": str(row["Ticker"]), "Week": date,
                                 "Wisdom_Rank": row["Pure_Momentum_Rank"],
                                 "Wisdom_Quality": row["Data_Quality"]})
    columns = list(events.columns) + ["Wisdom_Week", "Wisdom_Rank", "Wisdom_Quality"]
    if events.empty:
        return pd.DataFrame(columns=columns)
    history = pd.DataFrame(observations)
    if history.empty:
        return events.assign(Wisdom_Week=None, Wisdom_Rank=None, Wisdom_Quality=None)
    left = events.copy()
    left["_session"] = pd.to_datetime(left["Session"], errors="raise").dt.normalize()
    left["_row"] = range(len(left))
    # Strictly earlier observation, not same-day; conservative against publish-time ambiguity.
    history["Week"] = history["Week"] + pd.Timedelta(days=1)
    joined = pd.merge_asof(left.sort_values("_session"), history.sort_values("Week"),
                           left_on="_session", right_on="Week", by="Symbol",
                           direction="backward", allow_exact_matches=False)
    joined["Wisdom_Week"] = (joined["Week"] - pd.Timedelta(days=1)).dt.strftime("%Y-%m-%d")
    return joined.sort_values("_row").drop(columns=["_row", "_session", "Week"])[columns]


def leadership_breakout_summary(linked, *, top_rank=50):
    """Descriptive comparison only; missing prior ranks never become nonleaders."""
    required = {"Wisdom_Rank", "Outcome", "Symbol"}
    if not required.issubset(linked.columns):
        raise ValueError("Missing linked outcome fields")
    frame = linked.copy()
    frame["Wisdom_Rank"] = pd.to_numeric(frame["Wisdom_Rank"], errors="coerce")
    frame["Group"] = "NO_PRIOR_RANK"
    valid = frame["Wisdom_Rank"].notna() & (frame["Wisdom_Rank"] > 0)
    frame.loc[valid & (frame["Wisdom_Rank"] <= top_rank), "Group"] = f"TOP_{top_rank}"
    frame.loc[valid & (frame["Wisdom_Rank"] > top_rank), "Group"] = "OTHER_RANKED"
    results = []
    for group in (f"TOP_{top_rank}", "OTHER_RANKED", "NO_PRIOR_RANK"):
        cohort = frame[frame["Group"] == group]
        successes = int((cohort["Outcome"] == "SUCCESS").sum())
        failures = int(cohort["Outcome"].isin(["FAILURE", "STOP_BREACH"]).sum())
        resolved = successes + failures
        results.append({"Prior_Leadership": group, "Breakouts": len(cohort),
                        "Resolved": resolved, "Successes": successes,
                        "Failures_Incl_Stops": failures,
                        "Stop_Breaches": int((cohort["Outcome"] == "STOP_BREACH").sum()),
                        "Unresolved": len(cohort) - resolved,
                        "Success_Rate_Pct": round(100 * successes / resolved, 1) if resolved else None})
    return pd.DataFrame(results)
