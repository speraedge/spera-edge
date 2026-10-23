"""Local research-only saved trade plans. Not a durable multi-user ledger."""
import math
import re
from datetime import date



def validate_plan(symbol, pivot, stop, target, setup_date):
    symbol = str(symbol).strip().upper()
    if not re.fullmatch(r"[A-Z0-9&_.-]{1,30}", symbol):
        raise ValueError("Invalid symbol")
    numbers = [float(x) for x in (pivot, stop, target)]
    if not all(math.isfinite(x) and x > 0 for x in numbers):
        raise ValueError("Finite positive levels required")
    pivot, stop, target = numbers
    if not stop < pivot < target:
        raise ValueError("Require Stop < Pivot < Target")
    session = date.fromisoformat(str(setup_date)).isoformat()
    return {"Symbol": symbol, "Setup Date": session, "Pivot": pivot, "Stop": stop, "Target": target}


def status(plan, price):
    try:
        current = float(price)
    except (TypeError, ValueError):
        return "NO_PRICE"
    if not math.isfinite(current) or current <= 0:
        return "NO_PRICE"
    if current < plan["Stop"]:
        return "INVALID"
    if current > plan["Pivot"] * 1.05:
        return "EXTENDED"
    if current > plan["Pivot"] * 1.01:
        return "TRIGGERED"
    return "WAITING"


def evaluate_plans(plans, prices):
    rows = []
    for plan in plans:
        current = prices.get(plan["Symbol"])
        state = status(plan, current)
        if state != "INVALID":
            rows.append(dict(plan, **{"Current Price": current, "Status": state}))
    return rows


class OwnerPlanStore:
    """All D1 access requires an authenticated, allowlisted owner and parameterized owner filter."""
    def __init__(self, owner, query):
        if not isinstance(owner, str) or not owner.strip() or not callable(query):
            raise ValueError("Authenticated owner and D1 query required")
        self.owner, self.query = owner, query

    def initialize(self):
        self.query("""CREATE TABLE IF NOT EXISTS edge_saved_plans (
            owner_id TEXT NOT NULL,
            plan_id TEXT NOT NULL,
            symbol TEXT NOT NULL,
            setup_date TEXT NOT NULL,
            pivot REAL NOT NULL,
            stop REAL NOT NULL,
            target REAL NOT NULL,
            status TEXT NOT NULL DEFAULT 'ACTIVE',
            created_utc TEXT NOT NULL,
            invalidated_utc TEXT,
            PRIMARY KEY (owner_id, plan_id),
            CHECK (stop > 0 AND stop < pivot AND pivot < target),
            CHECK (status IN ('ACTIVE', 'INVALID'))
        )""")

    def list_active(self):
        records = self.query(
            "SELECT plan_id, symbol, setup_date, pivot, stop, target FROM edge_saved_plans WHERE owner_id=? AND status='ACTIVE' ORDER BY setup_date DESC, plan_id",
            (self.owner,))
        return [dict(validate_plan(r["symbol"], r["pivot"], r["stop"], r["target"], r["setup_date"]),
                     plan_id=r["plan_id"]) for r in records]

    def add(self, plan):
        from uuid import uuid4
        from datetime import datetime, timezone
        checked = validate_plan(plan["Symbol"], plan["Pivot"], plan["Stop"], plan["Target"], plan["Setup Date"])
        plan_id = str(uuid4())
        self.query("""INSERT INTO edge_saved_plans
            (owner_id, plan_id, symbol, setup_date, pivot, stop, target, status, created_utc)
            VALUES (?, ?, ?, ?, ?, ?, ?, 'ACTIVE', ?)""",
            (self.owner, plan_id, checked["Symbol"], checked["Setup Date"], checked["Pivot"],
             checked["Stop"], checked["Target"], datetime.now(timezone.utc).isoformat()))
        return plan_id

    def invalidate(self, plan_id):
        from datetime import datetime, timezone
        self.query("""UPDATE edge_saved_plans SET status='INVALID', invalidated_utc=?
            WHERE owner_id=? AND plan_id=? AND status='ACTIVE'""",
            (datetime.now(timezone.utc).isoformat(), self.owner, plan_id))

    def load_active(self, plan_id):
        records = self.query("""SELECT plan_id, symbol, setup_date, pivot, stop, target
            FROM edge_saved_plans WHERE owner_id=? AND plan_id=? AND status='ACTIVE'""",
            (self.owner, plan_id))
        if len(records) != 1:
            raise ValueError("Plan not found for authorized owner")
        r = records[0]
        return dict(validate_plan(r["symbol"], r["pivot"], r["stop"], r["target"], r["setup_date"]),
                    plan_id=r["plan_id"])
