"""Local research-only saved trade plans. Not a durable multi-user ledger."""
import json
import math
import os
import re
import tempfile
from datetime import date
from pathlib import Path

PLAN_FILE = Path(__file__).resolve().parents[1] / "data" / "latest" / "saved_plans.json"


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


def load_plans(path=PLAN_FILE):
    path = Path(path)
    if not path.exists():
        return []
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, list) or len(raw) > 1000:
        raise ValueError("Invalid saved plans file")
    return [validate_plan(x["Symbol"], x["Pivot"], x["Stop"], x["Target"], x["Setup Date"]) for x in raw]


def save_plans(plans, path=PLAN_FILE):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    # Atomic replace avoids truncated files on interrupted writes.
    with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent,
                                     prefix=".plans-", suffix=".tmp", delete=False) as f:
        temp = Path(f.name)
        json.dump(plans, f, indent=2, allow_nan=False)
    try:
        os.replace(temp, path)
    finally:
        temp.unlink(missing_ok=True)


def add_plan(plan, path=PLAN_FILE):
    checked = validate_plan(plan["Symbol"], plan["Pivot"], plan["Stop"],
                            plan["Target"], plan["Setup Date"])
    plans = load_plans(path)
    if any(x["Symbol"] == checked["Symbol"] and x["Setup Date"] == checked["Setup Date"] for x in plans):
        raise ValueError("Plan already saved for this symbol and date")
    plans.append(checked)
    save_plans(plans, path)
    return checked


def status(plan, price):
    try:
        current = float(price)
    except (TypeError, ValueError):
        return "NO_PRICE"
    if not math.isfinite(current) or current <= 0:
        return "NO_PRICE"
    pivot, stop = plan["Pivot"], plan["Stop"]
    if current < stop:
        return "INVALID"
    if current > pivot * 1.05:
        return "EXTENDED"
    if current > pivot * 1.01:
        return "TRIGGERED"
    return "WAITING"


def evaluate_plans(plans, prices):
    rows, active = [], []
    for plan in plans:
        current = prices.get(plan["Symbol"])
        state = status(plan, current)
        if state == "INVALID":
            continue
        active.append(plan)
        rows.append(dict(plan, **{"Current Price": current, "Status": state}))
    return rows, active
