"""Forward price observations for dated setup decisions, not executable returns."""
import math
import pandas as pd

def decision_outcomes(decisions, close, horizon=10, *, as_of=None):
    if (type(horizon) is not int or horizon < 1 or close.columns.has_duplicates
            or close.index.has_duplicates or not close.index.is_monotonic_increasing):
        raise ValueError("Invalid horizon or market sessions")
    dates = pd.to_datetime(close.index)
    if dates.isna().any() or dates.has_duplicates:
        raise ValueError('Invalid market session dates')
    if as_of is not None:
        cutoff = pd.Timestamp(as_of)
        if pd.isna(cutoff):
            raise ValueError('Invalid observation cutoff')
        close = close.loc[dates <= cutoff]
        dates = dates[dates <= cutoff]
    rows = []
    for decision in decisions:
        symbol = decision["symbol"]
        session = pd.Timestamp(decision["session"])
        record = {"decision_id": decision["decision_id"], "Symbol": symbol,
                  "Decision_Session": str(session.date()), "Decision": decision["decision"],
                  "Horizon": horizon, "Observation": "UNAVAILABLE",
                  "Reference_Close": None, "Future_Close": None, "Forward_Change_Pct": None,
                  "Observed_Session": None}
        # A decision is anchored only to the exact recorded completed session.
        if symbol not in close.columns:
            record["Observation"] = "SYMBOL_NOT_IN_SNAPSHOT"
        else:
            index = dates.get_indexer([session])[0]
            if index < 0:
                record["Observation"] = "SESSION_NOT_IN_SNAPSHOT"
            else:
                reference = pd.to_numeric(close[symbol].iloc[index], errors="coerce")
                if not math.isfinite(reference) or reference <= 0:
                    record["Observation"] = "INVALID_REFERENCE_PRICE"
                elif index + horizon >= len(dates):
                    record["Observation"] = "AWAITING_FUTURE_SESSIONS"
                    record["Reference_Close"] = float(reference)
                else:
                    future = pd.to_numeric(close[symbol].iloc[index + horizon], errors="coerce")
                    record["Reference_Close"] = float(reference)
                    if not math.isfinite(future) or future <= 0:
                        record["Observation"] = "INVALID_FUTURE_PRICE"
                    else:
                        record.update(Observation="OBSERVED", Future_Close=float(future),
                                      Observed_Session=str(dates[index+horizon].date()),
                                      Forward_Change_Pct=round(100*(float(future)/float(reference)-1), 4))
        rows.append(record)
    return pd.DataFrame(rows, columns=["decision_id", "Symbol", "Decision_Session",
        "Decision", "Horizon", "Observation", "Reference_Close", "Future_Close",
        "Forward_Change_Pct", "Observed_Session"])
