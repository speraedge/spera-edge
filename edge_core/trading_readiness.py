"""Fail-closed trader-facing research handoff; never issues a buy signal.

Uses existing frozen-scored leadership output without modifying its formulas.
Financial evidence is a separate gate and cannot promote a technical candidate.
"""
from edge_core.evidence_shortlist import evidence_shortlist
from edge_core.manual_evidence_queue import build_queue
from edge_core.acquisition_review_import import validate_acquisition_import
from edge_core.portfolio import position_size
from edge_core.portfolio_risk import risk_budget

def trading_readiness(scored, membership, financial_records, period_end, *, acquisition=None, technical_evidence=None, snapshot_fresh=False, setup_evidence=None, risk_inputs=None):
    """Return auditable per-company research status and explicit missing gates."""
    shortlist = evidence_shortlist(scored, membership)
    queue = build_queue(shortlist, financial_records, period_end)
    verified_acquisition = {}
    if acquisition is not None and queue:
        checked = validate_acquisition_import(acquisition, queue)
        verified_acquisition = {
            (x["symbol"], x["isin"]): x["acquisition_status"] for x in checked
        }
    technical = {}
    if technical_evidence is not None:
        required = {"Symbol", "Price_Template_Pass", "RS_80th_Percentile_Diagnostic"}
        if not required.issubset(technical_evidence.columns):
            raise ValueError("Missing technical qualification evidence")
        if technical_evidence["Symbol"].duplicated().any():
            raise ValueError("Duplicate technical qualification symbol")
        technical = {row["Symbol"]: row for _, row in technical_evidence.iterrows()}
    setups = {}
    if setup_evidence is not None:
        required = {"Ticker", "VCP_Setup", "VCP_Score"}
        if not required.issubset(setup_evidence.columns):
            raise ValueError("Missing setup scanner evidence")
        if setup_evidence["Ticker"].duplicated().any():
            raise ValueError("Duplicate setup scanner ticker")
        setups = {str(row["Ticker"]).strip().upper(): row
                  for _, row in setup_evidence.iterrows()}
    risk_plan = None
    if risk_inputs is not None:
        required = {"capital", "risk_pct", "entry", "stop", "committed_risk"}
        if not isinstance(risk_inputs, dict) or not required.issubset(risk_inputs):
            raise ValueError("Incomplete risk planning inputs")
        if not snapshot_fresh:
            raise ValueError("Risk planning requires a fresh validated snapshot")
        budget = risk_budget(risk_inputs["capital"], risk_inputs["risk_pct"],
                             risk_inputs["committed_risk"])
        sizing = position_size(risk_inputs["capital"], risk_inputs["risk_pct"],
                               risk_inputs["entry"], risk_inputs["stop"])
        max_qty = int(budget["new_trade_budget"] // sizing["risk_per_share"])
        qty = min(sizing["quantity"], max_qty)
        risk_plan = {"quantity": qty, "planned_risk": qty * sizing["risk_per_share"],
                     "available_risk": budget["available_risk"],
                     "portfolio_ceiling": budget["portfolio_ceiling"],
                     "research_only": True}
    rows = []
    for candidate, request in zip(shortlist, queue):
        if (candidate["symbol"], candidate["isin"]) != (request["symbol"], request["isin"]):
            raise ValueError("Shortlist and evidence queue identity mismatch")
        status = verified_acquisition.get((candidate["symbol"], candidate["isin"]),
                                          "NOT_IMPORTED")
        evidence = technical.get(candidate["symbol"])
        template = (evidence is not None and evidence["Price_Template_Pass"] == True)
        rs = (evidence is not None and evidence["RS_80th_Percentile_Diagnostic"] == True)
        setup = setups.get(candidate["symbol"])
        setup_review = setup is not None and bool(str(setup["VCP_Setup"]).strip())
        gates = {
            "market_breadth": "RESEARCH_AVAILABLE_UNCERTIFIED" if snapshot_fresh else "NOT_VERIFIED",
            "technical_leadership": candidate["technical_data_quality"],
            "sepa_trend_template": "PASS_RESEARCH_ONLY" if template else "NOT_VERIFIED",
            "relative_strength": "PASS_RESEARCH_ONLY" if rs else "NOT_VERIFIED",
            "vcp_pivot_volume": "SETUP_RESEARCH_ONLY" if setup_review else "NOT_VERIFIED",
            "financial_evidence": "REVIEW_REQUIRED",
            "corporate_actions": "NOT_VERIFIED",
            "trade_risk": "SIZING_RESEARCH_ONLY" if risk_plan is not None else "NOT_VERIFIED",
        }
        rows.append({
            "symbol": candidate["symbol"], "isin": candidate["isin"],
            "research_percentile": candidate["research_percentile"],
            "evidence_reason": request["reason"],
            "acquisition_status": status, "gates": gates,
            "setup_score": float(setup["VCP_Score"]) if setup_review else None,
            "risk_plan": risk_plan,
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
