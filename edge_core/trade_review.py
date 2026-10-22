"""Private journal quality diagnostics; never joins research outcomes to fills by symbol alone."""
import pandas as pd


def journal_quality(events):
    """Summarize recorded activity without guessing fills, timestamps or profitability."""
    columns = ["Symbol", "Buys", "Sells", "Stop_Updates", "Notes", "Buys_Without_Notes",
               "Review_Status"]
    if not events:
        return pd.DataFrame(columns=columns)
    rows = []
    symbols = sorted({str(e.get("symbol", "")).strip().upper() for e in events if e.get("symbol")})
    for symbol in symbols:
        items = [e for e in events if str(e.get("symbol", "")).strip().upper() == symbol]
        buys = [e for e in items if e.get("kind") == "BUY"]
        sells = [e for e in items if e.get("kind") == "SELL"]
        stops = [e for e in items if e.get("kind") == "STOP"]
        notes = [e for e in items if e.get("kind") == "NOTE"]
        undocumented = sum(not str(e.get("note") or "").strip() for e in buys)
        status = "REVIEW_NEEDED" if undocumented else ("DOCUMENTED_BUYS" if buys else "NO_BUYS")
        rows.append({"Symbol": symbol, "Buys": len(buys), "Sells": len(sells),
                     "Stop_Updates": len(stops), "Notes": len(notes),
                     "Buys_Without_Notes": undocumented, "Review_Status": status})
    return pd.DataFrame(rows, columns=columns)
