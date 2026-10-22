"""Read-only source-contract audit for SPERA EDGE's five-tab application.

This is a static integration preflight, NOT a live Streamlit, D1 or trading
certification. Run from repository root:
    python tools/verify_dashboard_acceptance.py
"""
from __future__ import annotations

import ast
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXPECTED_TABS = [
    "Market Pulse",
    "Leadership Scanner",
    "Trade Desk",
    "Portfolio & Journal",
    "Financial Evidence Review",
]


def check() -> dict:
    failures = []
    app_path = ROOT / "app.py"
    source = app_path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(app_path))

    tabs = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if not isinstance(node.func, ast.Attribute) or node.func.attr != "tabs":
            continue
        if not isinstance(node.func.value, ast.Name) or node.func.value.id != "st":
            continue
        if node.args and isinstance(node.args[0], (ast.List, ast.Tuple)):
            tabs.extend(
                element.value for element in node.args[0].elts
                if isinstance(element, ast.Constant) and isinstance(element.value, str)
            )
    if tabs != EXPECTED_TABS:
        failures.append(f"Expected five ordered tabs, got {tabs!r}")

    required_imports = {
        "edge_core.momentum_v1": "apply_frozen_v1_scores",
        "edge_core.ohlcv_integrity": "snapshot_is_fresh",
        "edge_core.snapshot_integrity": "validate_snapshot",
        "edge_trader_readiness_ui": "render_trader_readiness",
        "edge_financial_review": "render_financial_evidence_review",
    }
    imports = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            imports.setdefault(node.module, set()).update(alias.name for alias in node.names)
    for module, symbol in required_imports.items():
        if symbol not in imports.get(module, set()):
            failures.append(f"Missing application import: {module}.{symbol}")

    required_files = [
        "edge_core/trading_readiness.py",
        "edge_core/portfolio_risk.py",
        "edge_core/decision_outcomes.py",
        "edge_core/historical_replay.py",
        "edge_workspace.py",
        "edge_exports.py",
        "edge_financial_review.py",
        "edge_trader_readiness_ui.py",
    ]
    for name in required_files:
        if not (ROOT / name).is_file():
            failures.append(f"Missing integration module: {name}")

    readiness = (ROOT / "edge_core/trading_readiness.py").read_text(encoding="utf-8")
    if '"ready_for_trading_signals": False' not in readiness and "'ready_for_trading_signals': False" not in readiness:
        # Permit alternate formatting only after a human reviews the gate.
        failures.append("Cannot statically verify readiness remains non-trading")
    if "snapshot_is_fresh(" not in source or "validate_snapshot(" not in source:
        failures.append("App lacks explicit snapshot integrity/freshness calls")

    return {
        "status": "PASS" if not failures else "FAIL",
        "audit": "static_five_tab_source_preflight",
        "tabs": tabs,
        "failures": failures,
        "live_verified": False,
        "certified": False,
        "limitations": [
            "Does not execute Streamlit widgets or inspect their rendered output",
            "Does not verify Upstox, Cloudflare D1, OIDC, downloads or real market data",
            "Does not certify trading readiness, financial evidence or backtest results",
        ],
    }


if __name__ == "__main__":
    result = check()
    print(json.dumps(result, indent=2))
    raise SystemExit(0 if result["status"] == "PASS" else 1)
