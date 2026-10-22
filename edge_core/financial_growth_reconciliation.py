"""Fail-closed reconciliation of financial growth with identity audit."""
import csv
import json
from collections import Counter
from pathlib import Path

def reconcile_financial_growth(review_csv, candidates_csv, output_dir):
    def read(path):
        with Path(path).open(newline="", encoding="utf-8-sig") as f:
            return list(csv.DictReader(f))
    reviews = read(review_csv)
    candidates = read(candidates_csv)
    if len(reviews) != len(candidates):
        raise ValueError("Financial review and candidate row counts differ")
    identity = {}
    for item in reviews:
        key = item["row"]
        if key in identity:
            raise ValueError("Duplicate financial review row")
        identity[key] = item
    findings = []
    for item in candidates:
        source = identity.get(item["row"])
        if source is None or source["symbol"] != item["symbol"] or source["isin"] != item["isin"]:
            raise ValueError("Financial identity mismatch")
        allowed = (source["status"] == "REVIEW_SOURCE_AND_COMPARABILITY"
                   and item["status"] == "CANDIDATE_COMPARABLE_UNVERIFIED")
        findings.append({"row": item["row"], "symbol": item["symbol"],
                         "status": "CANDIDATE_UNCERTIFIED" if allowed else "BLOCKED",
                         "revenue_growth_candidate_pct": item["revenue_growth_candidate_pct"] if allowed else "",
                         "pat_growth_candidate_pct": item["pat_growth_candidate_pct"] if allowed else "",
                         "certified": False})
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    columns = ["row", "symbol", "status", "revenue_growth_candidate_pct",
               "pat_growth_candidate_pct", "certified"]
    with (out / "financial_growth_reconciliation.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=columns)
        writer.writeheader()
        writer.writerows(findings)
    summary = {"rows": len(findings), "status_counts": dict(Counter(x["status"] for x in findings)),
               "certified": False, "ready_for_trading_signals": False}
    (out / "financial_growth_reconciliation_summary.json").write_text(json.dumps(summary, indent=2))
    return summary
