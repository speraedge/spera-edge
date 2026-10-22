"""Offline SPERA EDGE manual-evidence workflow.

Example:
 python -m tools.manual_evidence_workflow --shortlist candidates.csv --membership membership.csv --financials financials.csv --period-end 2026-09-30 --output data/evidence_review/manual
Optionally supply --submissions to validate operator entries against generated requests.
No network calls, D1 writes, source certification, or frozen Momentum V1 changes.
"""
import argparse
import csv
import json
from pathlib import Path
from edge_core.manual_evidence_queue import build_queue, write_queue
from edge_core.manual_evidence_intake import review_csv


def read_csv(path):
    with Path(path).open(newline="", encoding="utf-8-sig") as stream:
        return list(csv.DictReader(stream))


def execute(shortlist_path, membership_path, financials_path, period_end, output,
            submissions_path=None, period_type="Q", basis="CONSOLIDATED"):
    membership = read_csv(membership_path)
    identities = {}
    for row in membership:
        symbol = str(row.get("Symbol", "")).strip().upper()
        isin = str(row.get("ISIN Code", "")).strip().upper()
        if not symbol or not isin or symbol in identities:
            raise ValueError("Membership identity missing or duplicated")
        identities[symbol] = isin
    shortlist = []
    for row in read_csv(shortlist_path):
        symbol = str(row.get("Symbol", row.get("symbol", ""))).strip().upper()
        if symbol not in identities:
            raise ValueError("Shortlist symbol not in official membership: " + symbol)
        # Ignore user-provided ISIN in favor of checked membership identity.
        shortlist.append({"symbol": symbol, "isin": identities[symbol]})
    records = read_csv(financials_path)
    out = Path(output)
    out.mkdir(parents=True, exist_ok=True)
    queue = build_queue(shortlist, records, period_end, period_type, basis)
    write_queue(out / "manual_evidence_queue.csv", queue)
    result = {"queue_rows": len(queue), "certified": False,
              "review_required": len(queue), "source_verification_complete": False}
    if submissions_path:
        findings = review_csv(out / "manual_evidence_queue.csv", submissions_path,
                              out / "manual_evidence_intake_review.csv")
        result["intake_rows"] = len(findings)
        result["quarantined"] = sum(x["intake_status"] == "QUARANTINED_UNVERIFIED" for x in findings)
        result["rejected"] = sum(x["intake_status"] == "REJECTED" for x in findings)
    (out / "manual_evidence_summary.json").write_text(json.dumps(result, indent=2))
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for flag in ("shortlist", "membership", "financials", "period-end", "output"):
        parser.add_argument("--" + flag, required=True)
    parser.add_argument("--submissions")
    parser.add_argument("--period-type", choices=("Q", "FY"), default="Q")
    parser.add_argument("--basis", choices=("CONSOLIDATED", "STANDALONE"), default="CONSOLIDATED")
    args = parser.parse_args()
    print(json.dumps(execute(args.shortlist, args.membership, args.financials,
                             args.period_end, args.output, args.submissions,
                             args.period_type, args.basis), indent=2))


if __name__ == "__main__":
    main()
