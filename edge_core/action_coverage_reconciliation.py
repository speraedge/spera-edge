"""Reconcile dated corporate actions to monthly historical source coverage.

This module is a research gate only. A registered month is not proof that
an event was published correctly or that price adjustments are authorized.
"""
import csv
import json
from collections import Counter
from datetime import date
from pathlib import Path


def reconcile_action_coverage(actions_review_csv, coverage_csv, output_dir):
    with Path(coverage_csv).open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        if not reader.fieldnames or not {"month", "status"}.issubset(reader.fieldnames):
            raise ValueError("Coverage CSV requires month and status")
        coverage = {}
        for record in reader:
            month = str(record["month"]).strip()
            if month in coverage:
                raise ValueError("Duplicate coverage month")
            coverage[month] = str(record["status"]).strip()
    with Path(actions_review_csv).open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        if not reader.fieldnames or not {"row", "symbol", "ex_date", "status"}.issubset(reader.fieldnames):
            raise ValueError("Corporate action review missing required columns")
        actions = list(reader)
    findings = []
    for action in actions:
        raw_date = str(action["ex_date"] or "").strip()
        try:
            month = date.fromisoformat(raw_date).strftime("%Y-%m")
        except ValueError:
            month = ""
        monthly = coverage.get(month, "MISSING_SOURCE")
        if not month:
            status = "INVALID_EVENT_DATE"
        elif monthly != "REVIEW_ASSERTED_COMPLETE":
            status = "HISTORICAL_COVERAGE_GAP"
        elif str(action["status"]) != "REVIEW_OFFICIAL_TERMS":
            status = "EVENT_EVIDENCE_UNRESOLVED"
        else:
            status = "REQUIRES_INDEPENDENT_EVENT_VERIFICATION"
        findings.append({"row": action["row"], "symbol": action["symbol"],
                         "ex_date": raw_date, "month": month,
                         "event_status": action["status"],
                         "coverage_status": monthly, "reconciliation_status": status,
                         "approved": False})
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    fields = ["row", "symbol", "ex_date", "month", "event_status",
              "coverage_status", "reconciliation_status", "approved"]
    with (out / "corporate_action_reconciliation.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(findings)
    summary = {"event_count": len(findings),
               "status_counts": dict(Counter(x["reconciliation_status"] for x in findings)),
               "verified_adjustment_factors": 0,
               "historical_price_adjustments_authorized": False,
               "certified": False}
    (out / "corporate_action_reconciliation_summary.json").write_text(json.dumps(summary, indent=2))
    return summary
