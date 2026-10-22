"""Consolidated Milestone 2 readiness report.

Technical reconciliation is not independent certification. Fail closed even
when every provisional review is present and numerically consistent.
"""
import json
from pathlib import Path


REQUIRED = ("corporate_actions", "financials", "financial_comparability",
            "financial_growth_reconciliation", "historical_coverage",
            "action_coverage_reconciliation", "filing_documents",
            "statement_document_reconciliation", "filing_value_reconciliation")


def assess_readiness(results, output_dir):
    missing = [name for name in REQUIRED if name not in results]
    present = [name for name in REQUIRED if name in results]
    unresolved = {}
    for name in present:
        section = results[name]
        counts = section.get("status_counts", {})
        unresolved[name] = {str(k): int(v) for k, v in counts.items() if int(v) > 0}
    assessment = {
        "required_sections": list(REQUIRED),
        "present_sections": present,
        "missing_sections": missing,
        "unresolved_status_counts": unresolved,
        "technical_audit_complete": not missing,
        "independent_source_verification_complete": False,
        "corporate_actions_certified": False,
        "financial_growth_certified": False,
        "historical_prices_adjusted_and_verified": False,
        "ready_for_trading_signals": False,
        "certified": False,
        "decision": "BLOCKED_PENDING_INDEPENDENT_EVIDENCE",
    }
    destination = Path(output_dir)
    destination.mkdir(parents=True, exist_ok=True)
    (destination / "milestone2_readiness.json").write_text(json.dumps(assessment, indent=2))
    return assessment
