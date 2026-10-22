"""Fail-closed reviewer decision for reconciled financial evidence.

This is an auditable *eligibility* decision, not automatic certification.
Independent source authentication and reviewer identity remain mandatory.
"""
from datetime import date

REQUIRED = {
    "document_status": "REVIEW_ORIGINAL_DOCUMENT",
    "statement_status": "MATCHED_DOCUMENT_UNCERTIFIED",
    "value_status": "VALUES_MATCH_UNVERIFIED_TRANSCRIPTION",
    "comparability_status": "CANDIDATE_COMPARABLE_UNVERIFIED",
}


def assess_financial_certification(candidate, *, reviewer=None, source_authenticated=False,
                                   figures_independently_checked=False):
    if not isinstance(candidate, dict):
        raise ValueError("Candidate must be a mapping")
    evidence = candidate.get("reconciliation")
    if not isinstance(evidence, dict):
        evidence = {}
    missing = [key for key, expected in REQUIRED.items()
               if evidence.get(key) != expected]
    if evidence.get("identity_status") != "FULL_IDENTITY_VERIFIED":
        missing.append("full_filing_identity_reconciliation")
    if candidate.get("acquisition_status") != "ACQUIRED_UNVERIFIED":
        missing.append("official_document_acquisition")
    try:
        published = date.fromisoformat(candidate["published_on"])
        period = date.fromisoformat(candidate["period_end"])
        if not period <= published <= date.today():
            missing.append("publication_chronology")
    except (ValueError, KeyError, TypeError):
        missing.append("publication_chronology")
    if source_authenticated is not True:
        missing.append("independent_source_authentication")
    if figures_independently_checked is not True:
        missing.append("independent_figure_verification")
    if not isinstance(reviewer, str) or not reviewer.strip():
        missing.append("identified_reviewer")
    return {
        "symbol": str(candidate.get("symbol", "")),
        "isin": str(candidate.get("isin", "")),
        "period_end": str(candidate.get("period_end", "")),
        "financial_certification_eligible": not missing,
        "missing_gates": missing,
        "certified": False,
        "ready_for_trading_signals": False,
        "decision": "READY_FOR_AUTHORIZED_SIGNOFF" if not missing else "REVIEW_REQUIRED",
    }
