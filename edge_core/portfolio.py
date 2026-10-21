"""Position sizing and research journal helpers. No brokerage integration."""
from datetime import datetime, timezone
import math
import pandas as pd

JOURNAL_COLUMNS = ["Timestamp_UTC", "Symbol", "Side", "Entry", "Stop", "Quantity", "Risk_Rupees", "Note"]

def position_size(capital, risk_pct, entry, stop):
    vals = (capital, risk_pct, entry, stop)
    if not all(math.isfinite(float(v)) for v in vals):
        raise ValueError("All inputs must be finite.")
    capital, risk_pct, entry, stop = map(float, vals)
    if capital <= 0 or not 0 < risk_pct <= 5 or entry <= 0 or stop <= 0 or entry == stop:
        raise ValueError("Enter positive capital/prices, distinct entry and stop, and risk 0-5%.")
    if stop >= entry:
        raise ValueError("Long position stop must be below entry.")
    risk_rupees = capital * risk_pct / 100
    per_share = abs(entry-stop)
    qty = min(math.floor(risk_rupees/per_share), math.floor(capital/entry))
    return {"quantity": qty, "risk_budget": risk_rupees, "risk_per_share": per_share, "planned_risk": qty*per_share, "notional": qty*entry}

def journal_entry(symbol, side, entry, stop, quantity, note):
    if not symbol or not str(symbol).replace("_","").isalnum() or side not in ("LONG","SHORT"):
        raise ValueError("Valid symbol and side are required.")
    if not isinstance(quantity,int) or quantity <= 0:
        raise ValueError("Quantity must be positive.")
    if not all(math.isfinite(float(v)) and float(v)>0 for v in (entry,stop)) or entry==stop:
        raise ValueError("Valid distinct positive entry and stop are required.")
    if (side=="LONG" and stop>=entry) or (side=="SHORT" and stop<=entry):
        raise ValueError("Stop must be below entry for long, above entry for short.")
    return {"Timestamp_UTC":datetime.now(timezone.utc).isoformat(),"Symbol":symbol.upper(),"Side":side,"Entry":float(entry),"Stop":float(stop),"Quantity":quantity,"Risk_Rupees":abs(entry-stop)*quantity,"Note":str(note)}
