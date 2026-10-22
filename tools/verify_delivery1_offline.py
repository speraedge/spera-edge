"""Delivery 1 offline operational acceptance: snapshot, five tabs and exports.

Run from repository root. This does not claim live Upstox, D1, OIDC,
scheduler or Streamlit-browser acceptance.
"""
from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pandas as pd

from edge_core.snapshot_integrity import validate_snapshot
from edge_core.ohlcv_integrity import snapshot_is_fresh
from edge_exports import export_bytes
from tools.verify_dashboard_acceptance import check as check_dashboard

ROOT = Path(__file__).resolve().parents[1]


def run() -> dict:
    checks = {}
    dashboard = check_dashboard()
    if dashboard["status"] != "PASS":
        raise AssertionError(f"Five-tab contract failed: {dashboard['failures']}")
    checks["five_tab_source_contract"] = "PASS"

    snapshot = validate_snapshot(ROOT / "data/latest")
    meta = json.loads((ROOT / "data/latest/metadata.json").read_text())
    if snapshot["retrieved"] < 495 or meta.get("certified") is not False:
        raise AssertionError("Research snapshot coverage/certification gate failed")
    checks["saved_snapshot_integrity"] = snapshot

    # Deterministic stale-data failure: no trading readiness from ancient dates.
    if snapshot_is_fresh("2020-01-02", pd.Timestamp("2026-10-22T18:00:00+05:30")):
        raise AssertionError("Stale snapshot was accepted")
    checks["stale_snapshot_fail_closed"] = "PASS"

    frame = pd.DataFrame({
        "Symbol": ["A", "B"],
        "Untrusted note": ["=HYPERLINK(\"https://example.invalid\")", "@SUM(1,2)"],
        "Unicode": ["₹ 100", "हिंदी & <test>"],
        "Number": [12.5, None],
    })
    for fmt, signature in (("CSV", b"\xef\xbb\xbf"), ("Excel", b"PK"), ("PDF", b"%PDF")):
        data = export_bytes(frame, fmt, "Delivery 1 operational export")
        if not data.startswith(signature) or len(data) < 100:
            raise AssertionError(f"Invalid {fmt} export")
        checks[f"{fmt.lower()}_export"] = {"bytes": len(data), "status": "PASS"}
        if fmt == "CSV":
            text = data.decode("utf-8-sig")
            if "'=HYPERLINK" not in text or "'@SUM" not in text:
                raise AssertionError("CSV formula injection not escaped")
        if fmt == "Excel":
            from openpyxl import load_workbook
            from io import BytesIO
            wb = load_workbook(BytesIO(data), read_only=True)
            ws = wb.active
            if ws.max_row != 3 or ws["C2"].data_type == "f" or ws["C3"].data_type == "f":
                raise AssertionError("Excel row count or formula-injection protection failed")
            wb.close()

    return {
        "status": "PASS",
        "scope": "offline_delivery_1",
        "checks": checks,
        "live_verified": False,
        "certified": False,
        "pending_external_acceptance": [
            "Upstox provider freshness and recovery",
            "Scheduled publication and independent D1 readback",
            "Authenticated Streamlit five-tab browser and mobile testing",
            "Live CSV/Excel/PDF download interactions",
            "Owner-scoped D1 and OIDC production smoke",
        ],
    }


if __name__ == "__main__":
    result = run()
    print(json.dumps(result, indent=2, default=str))
