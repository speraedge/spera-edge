"""Run both evidence audits against explicit CSV inputs and official membership.

This is a research audit, not a certification or a price-adjustment engine.
"""
import argparse
import json
from pathlib import Path
import pandas as pd
from edge_core.corporate_action_evidence import review_events
from edge_core.financial_evidence import review_financials
from edge_core.historical_evidence_coverage import audit_coverage
from edge_core.action_coverage_reconciliation import reconcile_action_coverage

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--membership", required=True,
                        help="Official NSE membership CSV containing Symbol and ISIN Code")
    parser.add_argument("--corporate-actions", help="Corporate-action evidence CSV")
    parser.add_argument("--financials", help="Financial statement evidence CSV")
    parser.add_argument("--coverage-register", help="Reviewed monthly historical source register CSV")
    parser.add_argument("--coverage-start", help="Inclusive YYYY-MM-DD")
    parser.add_argument("--coverage-end", help="Inclusive YYYY-MM-DD")
    parser.add_argument("--output", default="data/evidence_review")
    args = parser.parse_args()
    if bool(args.coverage_start) != bool(args.coverage_end):
        parser.error("Coverage start and end must both be supplied")
    if args.coverage_register and not args.coverage_start:
        parser.error("Coverage register requires start and end")
    if not args.corporate_actions and not args.financials and not args.coverage_register:
        parser.error("Supply at least one evidence CSV")
    membership = pd.read_csv(args.membership, dtype=str).fillna("")
    if not {"Symbol", "ISIN Code"}.issubset(membership.columns):
        parser.error("Membership needs Symbol and ISIN Code")
    membership["Symbol"] = membership["Symbol"].str.strip().str.upper()
    membership["ISIN Code"] = membership["ISIN Code"].str.strip().str.upper()
    if (membership["Symbol"].eq("").any() or membership["ISIN Code"].eq("").any()
            or membership["Symbol"].duplicated().any()
            or membership["ISIN Code"].duplicated().any()):
        parser.error("Official membership identities must be unique and nonempty")
    identities = dict(zip(membership["Symbol"], membership["ISIN Code"]))
    out = Path(args.output)
    result = {"certified": False, "adjusted_prices_ready": False,
              "financial_growth_ready": False}
    if args.corporate_actions:
        result["corporate_actions"] = review_events(args.corporate_actions, out / "actions", identities)
    if args.financials:
        result["financials"] = review_financials(args.financials, out / "financials", identities)
    if args.coverage_register:
        result["historical_coverage"] = audit_coverage(args.coverage_register, args.coverage_start,
                                                       args.coverage_end, out / "coverage")
    if args.corporate_actions and args.coverage_register:
        result["action_coverage_reconciliation"] = reconcile_action_coverage(
            out / "actions" / "corporate_action_review.csv",
            out / "coverage" / "historical_coverage.csv",
            out / "reconciliation")
    out.mkdir(parents=True, exist_ok=True)
    (out / "evidence_manifest.json").write_text(json.dumps(result, indent=2))
    print(json.dumps(result, indent=2))

if __name__ == "__main__":
    main()
