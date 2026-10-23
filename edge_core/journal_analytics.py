"""Owner-only journal analytics from explicit fills and observed dated marks.

No inferred trades, no forward-filled marks, no invented starting capital.
A single latest quote cannot reconstruct historical equity.
"""
import math
import pandas as pd

INSUFFICIENT_HISTORY = "INSUFFICIENT_HISTORY"


def _number(value):
    try:
        result = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    return result if math.isfinite(result) else None


def equity_curve(events, marks, *, initial_cash=None):
    """Reconstruct end-of-session equity using explicit fills and dated closing marks.

    marks: DataFrame indexed by actual observed sessions, columns are symbols.
    Cash changes only on BUY/SELL; all remaining positions require marks.
    Events require created_utc timestamps and are processed in ledger revision order.
    An event later than the last available mark is not silently ignored.
    """
    columns = ["Session", "Cash", "Market_Value", "Equity", "Realized_PnL"]
    capital = _number(initial_cash)
    if capital is None or capital <= 0 or not isinstance(marks, pd.DataFrame) or marks.empty:
        return pd.DataFrame(columns=columns), INSUFFICIENT_HISTORY
    if not isinstance(marks.index, pd.DatetimeIndex) or marks.index.has_duplicates or not marks.index.is_monotonic_increasing:
        return pd.DataFrame(columns=columns), INSUFFICIENT_HISTORY
    if marks.index.tz is not None:
        return pd.DataFrame(columns=columns), INSUFFICIENT_HISTORY
    sessions = marks.index.normalize()
    if sessions.has_duplicates or not sessions.equals(marks.index) or len(events) == 0:
        return pd.DataFrame(columns=columns), INSUFFICIENT_HISTORY
    ordered = sorted(events, key=lambda event: int(event.get("revision", 0)))
    if len({e.get("revision") for e in ordered}) != len(ordered):
        return pd.DataFrame(columns=columns), INSUFFICIENT_HISTORY
    for event in ordered:
        try:
            stamp = pd.Timestamp(event["created_utc"])
            if stamp.tzinfo is None or not all(k in event for k in ("kind", "symbol", "quantity", "price", "fee")):
                raise ValueError("Missing event metadata")
        except (KeyError, ValueError, TypeError, OverflowError):
            return pd.DataFrame(columns=columns), INSUFFICIENT_HISTORY
    # Dates are UTC calendar dates; do not assert an exchange-session timestamp.
    event_dates = [pd.Timestamp(e["created_utc"]).tz_convert("UTC").tz_localize(None).normalize() for e in ordered]
    if event_dates[0] < sessions[0] or event_dates[-1] > sessions[-1]:
        return pd.DataFrame(columns=columns), INSUFFICIENT_HISTORY
    if any(day not in sessions for day in event_dates):
        return pd.DataFrame(columns=columns), INSUFFICIENT_HISTORY
    cash, realized, holdings, rows, cursor = capital, 0.0, {}, [], 0
    for session in sessions:
        while cursor < len(ordered) and event_dates[cursor] == session:
            event = ordered[cursor]
            kind, symbol = event["kind"], event["symbol"]
            qty, price, fee = (_number(event.get(k)) for k in ("quantity", "price", "fee"))
            if None in (qty, price, fee) or fee < 0 or kind not in ("BUY", "SELL", "STOP", "NOTE"):
                return pd.DataFrame(columns=columns), INSUFFICIENT_HISTORY
            holding = holdings.setdefault(symbol, {"qty": 0, "cost": 0.0})
            if kind == "BUY":
                if qty <= 0 or int(qty) != qty or price <= 0:
                    return pd.DataFrame(columns=columns), INSUFFICIENT_HISTORY
                cash -= qty * price + fee
                holding["qty"] += int(qty)
                holding["cost"] += qty * price + fee
            elif kind == "SELL":
                if qty <= 0 or int(qty) != qty or price <= 0 or qty > holding["qty"]:
                    return pd.DataFrame(columns=columns), INSUFFICIENT_HISTORY
                basis = holding["cost"] * qty / holding["qty"]
                holding["qty"] -= int(qty)
                holding["cost"] -= basis
                cash += qty * price - fee
                realized += qty * price - fee - basis
            cursor += 1
        market_value = 0.0
        for symbol, holding in holdings.items():
            if holding["qty"] <= 0:
                continue
            if symbol not in marks.columns:
                return pd.DataFrame(columns=columns), INSUFFICIENT_HISTORY
            mark = _number(marks.at[session, symbol])
            if mark is None or mark <= 0:
                return pd.DataFrame(columns=columns), INSUFFICIENT_HISTORY
            market_value += holding["qty"] * mark
        rows.append({"Session": session, "Cash": cash, "Market_Value": market_value,
                     "Equity": cash + market_value, "Realized_PnL": realized})
    return pd.DataFrame(rows, columns=columns).set_index("Session"), "OK"


def max_drawdown(curve):
    if curve is None or curve.empty or "Equity" not in curve:
        return {"status": INSUFFICIENT_HISTORY}
    equity = pd.to_numeric(curve["Equity"], errors="coerce")
    if equity.isna().any() or (equity <= 0).any() or len(equity) < 2:
        return {"status": INSUFFICIENT_HISTORY}
    peaks = equity.cummax()
    dd = equity / peaks - 1
    trough = dd.idxmin()
    peak = equity.loc[:trough].idxmax()
    return {"status": "OK", "max_drawdown_pct": float(-dd.min() * 100),
            "peak_session": peak, "trough_session": trough,
            "drawdown_rupees": float(peaks.loc[trough] - equity.loc[trough])}


def r_multiples(events):
    """FIFO closed-lot realized R. Initial risk comes from each original BUY.

    Partial exits retain proportional original cost and risk; STOP updates do
    not change R. Fees are allocated to the exiting lots. Open lots excluded.
    """
    columns = ["Symbol", "Buy_Event_ID", "Sell_Event_ID", "Quantity", "Realized_PnL", "Original_Risk", "R_Multiple"]
    lots, rows = {}, []
    for event in sorted(events, key=lambda e: int(e.get("revision", 0))):
        kind = event.get("kind")
        symbol = event.get("symbol")
        if kind not in ("BUY", "SELL", "STOP", "NOTE") or not symbol:
            return pd.DataFrame(columns=columns), INSUFFICIENT_HISTORY
        if kind not in ("BUY", "SELL"):
            continue
        qty, price, fee = (_number(event.get(k)) for k in ("quantity", "price", "fee"))
        if None in (qty, price, fee) or qty <= 0 or int(qty) != qty or price <= 0 or fee < 0:
            return pd.DataFrame(columns=columns), INSUFFICIENT_HISTORY
        if kind == "BUY":
            stop = _number(event.get("stop"))
            if stop is None or not 0 < stop < price:
                return pd.DataFrame(columns=columns), INSUFFICIENT_HISTORY
            lots.setdefault(symbol, []).append({"qty": int(qty), "entry": price,
                "risk": price - stop, "fee_per_share": fee / qty, "event_id": event.get("event_id")})
        else:
            remaining = int(qty)
            queue = lots.get(symbol, [])
            while remaining:
                if not queue:
                    return pd.DataFrame(columns=columns), INSUFFICIENT_HISTORY
                lot = queue[0]
                used = min(remaining, lot["qty"])
                basis = used * (lot["entry"] + lot["fee_per_share"])
                pnl = used * price - fee * used / qty - basis
                original_risk = used * lot["risk"]
                rows.append({"Symbol": symbol, "Buy_Event_ID": lot["event_id"],
                    "Sell_Event_ID": event.get("event_id"), "Quantity": used,
                    "Realized_PnL": pnl, "Original_Risk": original_risk,
                    "R_Multiple": pnl / original_risk})
                remaining -= used
                lot["qty"] -= used
                if not lot["qty"]:
                    queue.pop(0)
    if not rows:
        return pd.DataFrame(columns=columns), INSUFFICIENT_HISTORY
    return pd.DataFrame(rows, columns=columns), "OK"


def expectancy(trades):
    if trades is None or trades.empty or "R_Multiple" not in trades:
        return {"status": INSUFFICIENT_HISTORY}
    multiples = pd.to_numeric(trades["R_Multiple"], errors="coerce")
    if multiples.isna().any() or not multiples.map(math.isfinite).all():
        return {"status": INSUFFICIENT_HISTORY}
    wins = multiples[multiples > 0]
    losses = multiples[multiples < 0]
    return {"status": "OK", "closed_lots": len(multiples),
        "win_rate_pct": float(len(wins) / len(multiples) * 100),
        "average_win_r": float(wins.mean()) if len(wins) else 0.0,
        "average_loss_r": float(losses.mean()) if len(losses) else 0.0,
        "expectancy_r": float(multiples.mean())}
