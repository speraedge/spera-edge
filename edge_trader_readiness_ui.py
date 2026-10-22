"""Read-only Streamlit bridge for integrated trader research readiness."""
import pandas as pd
import streamlit as st
from edge_core.momentum_v1 import apply_frozen_v1_scores
from edge_core.trading_readiness import trading_readiness
from edge_exports import numbered, export_section


def render_trader_readiness(leadership, membership, setups, period_end, *,
                            snapshot_fresh=False):
    """Show review-only candidates with explicit unresolved gates."""
    st.subheader("Integrated trading readiness")
    st.caption("Frozen Momentum V1 → price/RS research → VCP diagnostics → evidence gates. No buy signals.")
    if not snapshot_fresh:
        st.warning("Snapshot not fresh. Trading readiness and sizing unavailable.")
        return
    if leadership is None or membership is None:
        st.warning("Validated leadership and official ISIN membership required.")
        return
    scored = apply_frozen_v1_scores(leadership.copy())
    result = trading_readiness(scored, membership, [], period_end,
                               setup_evidence=setups, snapshot_fresh=True)
    if not result["candidates"]:
        st.info("No current research candidates satisfy the shortlist threshold.")
        return
    rows = []
    for candidate in result["candidates"]:
        row = {"Symbol": candidate["symbol"], "ISIN": candidate["isin"],
               "Momentum percentile": candidate["research_percentile"],
               "Decision": candidate["decision"],
               "Evidence reason": candidate["evidence_reason"],
               "VCP score": candidate["setup_score"]}
        row.update(candidate["gates"])
        rows.append(row)
    frame = pd.DataFrame(rows)
    st.dataframe(numbered(frame), use_container_width=True)
    export_section("Integrated readiness", frame, "integrated_readiness")
    st.warning("All candidates remain REVIEW_REQUIRED pending independent evidence and trade confirmation.")
