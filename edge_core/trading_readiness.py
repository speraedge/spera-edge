"""Fail-closed trader-facing research handoff; never issues a buy signal.

Uses existing frozen-scored leadership output without modifying its formulas.
Financial evidence is a separate gate and cannot promote a technical candidate.
"""
from edge_core.evidence_shortlist import evidence_shortlist
from edge_core.manual_evidence_queue import build_queue
from edge_core.acquisition_review_import import validate_acquisition_import

def trading_readiness(scored, membership, financial_records, period_end, *, acquisition=None):
    """Return auditable per-company research status and explicit missing gates."""
    shortlist = evidence_shortlist(scored, membership)
    queue = build_queue(shortlist, financial_records, period_end)
    verified_acquisition = {}
    if acquisition is not None and queue:
        checked = validate_acquisition_import(acquisition, queue)
        verified_acquisition = {
            (x["symbol"], x["isin"]): x["acquisition_status"] for x in checked
        }
    rows = []
    for candidate, request in zip(shortlist, queue):
        if (candidate["symbol"], candidate["isin"]) != (request["symbol"], request["isin"]):
            raise ValueError("Shortlist and evidence queue identity mismatch")
        status = verified_acquisition.get((candidate["symbol"], candidate["isin"]),
                                          "NOT_IMPORTED")
        gates = {
            "market_breadth": "NOT_VERIFIED",
            "technical_leadership": candidate["technical_data_quality"],
            "sepa_trend_template": "NOT_VERIFIED",
            "vcp_pivot_volume": "NOT_VERIFIED",
            "financial_evidence": "REVIEW_REQUIRED",
            "corporate_actions": "NOT_VERIFIED",
            "trade_risk": "NOT_VERIFIED",
        }
        rows.append({
            "symbol": candidate["symbol"], "isin": candidate["isin"],
            "research_percentile": candidate["research_percentile"],
            "evidence_reason": request["reason"],
            "acquisition_status": status, "gates": gates,
            "decision": "REVIEW_REQUIRED",
            "eligible_for_trading": False, "certified": False,
        })
    return {"candidate_count": len(rows), "candidates": rows,
            "certified": False, "ready_for_trading_signals": False,
            "limitations": [
                "Technical ranking alone is not a SEPA qualification",
                "Market breadth, VCP, corporate actions and risk require independent verification",
                "Official filing acquisition does not certify financial values",
            ]}
