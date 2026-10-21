"""SPERA EDGE: safe, read-only Streamlit application scaffold."""
import streamlit as st
import pandas as pd

st.set_page_config(page_title="SPERA EDGE", page_icon="📈", layout="wide")
st.title("SPERA EDGE")
st.caption("Independent momentum research • Prototype • No live trading")

tabs = st.tabs(["Market Pulse", "Leadership Scanner", "Trade Desk", "Portfolio & Journal"])
with tabs[0]:
    st.subheader("Market Pulse")
    st.info("Awaiting verified market breadth, benchmark history, and breakout outcome data. No regime is inferred without data.")
    for name in ("Stocks above 50 DMA", "Stocks above 200 DMA", "52-week highs", "Breakout success rate"):
        st.metric(name, "Not connected")
with tabs[1]:
    st.subheader("Leadership Scanner")
    st.info("Production momentum rankings are not yet imported or certified for this independent app.")
    st.dataframe(pd.DataFrame(columns=["Symbol", "Sector", "Momentum rank", "Stage 2", "As of"]), use_container_width=True)
with tabs[2]:
    st.subheader("Trade Desk")
    st.warning("VCP is a research heuristic, not a confirmed pattern. Validate every candidate on its chart.")
    st.dataframe(pd.DataFrame(columns=["Symbol", "Candidate reason", "Pivot", "Stop", "Risk %", "Review"]), use_container_width=True)
with tabs[3]:
    st.subheader("Portfolio & Journal")
    st.info("Manual journal UI is planned. No orders are sent to Upstox.")
    with st.form("journal"):
        symbol = st.text_input("Symbol").strip().upper()
        note = st.text_area("Research / journal note")
        submitted = st.form_submit_button("Preview journal entry")
        if submitted:
            if symbol and note.strip():
                st.success("Preview only — entry is not yet saved.")
                st.write({"symbol": symbol, "note": note})
            else:
                st.error("Enter both symbol and note.")
st.caption("Research tool only. No automated execution or return guarantees.")
