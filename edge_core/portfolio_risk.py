"""Pure research-only portfolio risk calculations."""
import math

def risk_budget(capital, risk_pct, committed_risk=0.0, ceiling_pct=5.0):
    values = [capital, risk_pct, committed_risk, ceiling_pct]
    if not all(math.isfinite(float(v)) for v in values):
        raise ValueError("Risk inputs must be finite")
    capital, risk_pct, committed_risk, ceiling_pct = map(float, values)
    if capital <= 0 or not 0 < risk_pct <= 5 or committed_risk < 0 or not 0 < ceiling_pct <= 100:
        raise ValueError("Invalid portfolio risk inputs")
    ceiling = capital * ceiling_pct / 100
    available = max(0.0, ceiling - committed_risk)
    return {"portfolio_ceiling": ceiling, "committed_risk": committed_risk,
            "available_risk": available,
            "new_trade_budget": min(capital * risk_pct / 100, available)}
