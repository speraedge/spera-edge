"""Research-only Indian equity execution gates; conservative estimates, not broker quotes."""
import math
import pandas as pd

MIN_ADTV_RUPEES = 5_00_00_000


def atr14(high, low, close):
    frame = pd.DataFrame({"h": high, "l": low, "c": close}).apply(pd.to_numeric, errors="coerce")
    if len(frame) < 15 or frame.tail(15).isna().any().any():
        raise ValueError("ATR requires 15 complete observed candles")
    if (frame.tail(15)[["h", "l", "c"]] <= 0).any().any() or (frame.tail(15).h < frame.tail(15).l).any():
        raise ValueError("Invalid observed candle")
    prev = frame.c.shift(1)
    tr = pd.concat([frame.h-frame.l, (frame.h-prev).abs(), (frame.l-prev).abs()], axis=1).max(axis=1)
    return float(tr.tail(14).mean())


def atr_stop(entry, high, low, close):
    entry = float(entry)
    if not math.isfinite(entry) or entry <= 0:
        raise ValueError("Invalid entry")
    distance = 2.5 * atr14(high, low, close)
    if not 0 < distance <= entry * 0.08:
        raise ValueError("ATR_STOP_TOO_WIDE")
    return entry - distance


def average_traded_value20(close, volume):
    frame = pd.DataFrame({"c": close, "v": volume}).apply(pd.to_numeric, errors="coerce").tail(20)
    if len(frame) != 20 or frame.isna().any().any() or (frame.c <= 0).any() or (frame.v < 0).any():
        raise ValueError("Missing or invalid 20-day liquidity data")
    return float((frame.c * frame.v).mean())


def require_liquidity(close, volume):
    if average_traded_value20(close, volume) < MIN_ADTV_RUPEES:
        raise ValueError("ADTV_BELOW_5_CRORE")
    return True


def net_reward_risk(entry, stop, target, quantity, *, roundtrip_cost_pct=0.006):
    """Conservative 0.6% round-trip cost allowance on entry notional.
    Includes estimated brokerage, STT, GST, other charges and slippage.
    Reconcile with broker schedule before execution.
    """
    values = [float(v) for v in (entry, stop, target, quantity, roundtrip_cost_pct)]
    entry, stop, target, quantity, rate = values
    if not all(map(math.isfinite, values)) or not 0 < stop < entry < target or quantity <= 0 or not 0 <= rate < 1:
        raise ValueError("Invalid net reward/risk inputs")
    risk = (entry-stop)*quantity
    costs = entry*quantity*rate
    net_reward = (target-entry)*quantity-costs
    return {"net_rr": net_reward/risk, "estimated_roundtrip_cost": costs,
            "net_reward": net_reward, "gross_risk": risk}


def require_earnings_clear(earnings_within_five_days):
    if earnings_within_five_days is not False:
        raise ValueError("EARNINGS_EVENT_GAP_RISK")
    return True


def trailing_stop_reminder(entry, initial_stop, latest_price, *, side="LONG"):
    if side != "LONG":
        return False
    values = [float(v) for v in (entry, initial_stop, latest_price)]
    if not all(map(math.isfinite, values)) or not 0 < initial_stop < entry:
        return False
    return latest_price >= entry + 2*(entry-initial_stop)
