"""SPERA EDGE: private, read-only research interface. No brokerage orders."""
import io
import pandas as pd
import streamlit as st
from edge_core.analytics import stage2_template, market_breadth
from edge_core.momentum_v1 import apply_frozen_v1_scores
from edge_core.setup_scanner import compute_setup_scanner, setup_scanner_coverage

st.set_page_config(page_title="SPERA EDGE", page_icon="📈", layout="wide")
st.title("SPERA EDGE")
st.caption("Independent research • Offline data-import mode • No brokerage execution")

def load_prices(upload):
    if upload is None:
        return None
    raw = pd.read_csv(io.BytesIO(upload.getvalue()))
    if "Date" not in raw.columns:
        raise ValueError("Price CSV must include Date and one or more symbol columns.")
    dates = pd.to_datetime(raw.pop("Date"), errors="coerce")
    if dates.isna().any() or dates.duplicated().any():
        raise ValueError("Dates must be valid and unique.")
    raw.index = dates
    return raw.apply(pd.to_numeric, errors="coerce").sort_index()

def upload_frame(label, key):
    obj = st.file_uploader(label, type=["csv"], key=key)
    if obj is None:
        return None
    try:
        return load_prices(obj)
    except (ValueError, pd.errors.ParserError) as exc:
        st.error(str(exc))
        return None

tabs = st.tabs(["Market Pulse", "Leadership Scanner", "Trade Desk", "Portfolio & Journal"])
with tabs[0]:
    st.subheader("Market Pulse")
    st.caption("Upload coherent daily close prices (Date, SYMBOL.NS columns). No live data is assumed.")
    prices = upload_frame("Daily close history CSV", "breadth")
    if prices is not None:
        stats = market_breadth(prices)
        st.metric("Symbols provided", stats["coverage"])
        a,b=st.columns(2)
        a.metric("Above 50 DMA", f'{stats["above_50_pct"]}%' if stats["above_50_pct"] is not None else "Insufficient history")
        b.metric("Above 200 DMA", f'{stats["above_200_pct"]}%' if stats["above_200_pct"] is not None else "Insufficient history")
        st.caption(f'50-day coverage: {stats["eligible_50"]}; 200-day coverage: {stats["eligible_200"]}. No regime is inferred.')
    else:
        st.info("No validated market history connected.")
with tabs[1]:
    st.subheader("Leadership Scanner")
    st.caption("Import one coherent universe cross-section with Data_Quality, Ret_6M, Ret_12M, AnnVol. Returns must be decimal fractions.")
    ranks = st.file_uploader("Momentum cross-section CSV", type=["csv"], key="ranks")
    if ranks:
        try:
            frame = pd.read_csv(ranks)
            required={"Data_Quality","Ret_6M","Ret_12M","AnnVol"}
            if not required.issubset(frame.columns):
                st.error("Missing columns: " + ", ".join(sorted(required-set(frame.columns))))
            elif len(frame) < 2:
                st.warning("At least two stocks required for cross-sectional z-scores.")
            else:
                frame["Ret_6M"]=pd.to_numeric(frame["Ret_6M"],errors="coerce")
                frame["Ret_12M"]=pd.to_numeric(frame["Ret_12M"],errors="coerce")
                frame["AnnVol"]=pd.to_numeric(frame["AnnVol"],errors="coerce")
                scored=apply_frozen_v1_scores(frame)
                trusted=scored.loc[scored["Data_Quality"].eq("PASS")].sort_values("Pure_Momentum_Rank").head(50)
                st.metric("Trusted PASS stocks", int(scored["Data_Quality"].eq("PASS").sum()))
                st.dataframe(trusted, use_container_width=True)
                st.download_button("Download ranked research CSV", scored.to_csv(index=False), "edge_ranked_research.csv", "text/csv")
                st.caption("Imported data is not independently certified. REVIEW/FAIL are not in the trusted list.")
        except Exception as exc:
            st.error(f"Unable to score input: {exc}")
    st.divider()
    stage_close=upload_frame("Optional close history for price-only Stage 2 checks", "stage2")
    if stage_close is not None and not stage_close.empty:
        records=[]
        for sym in stage_close:
            res=stage2_template(stage_close[sym])
            records.append({"Symbol":sym,"Price-template pass":res["eligible"],"Note":res["reason"]})
        st.dataframe(pd.DataFrame(records), use_container_width=True)
        st.caption("Stage 2 relative-strength requirement must be verified separately. Price-only pass is not full Stage 2 qualification.")
with tabs[2]:
    st.subheader("Trade Desk")
    st.warning("Research candidates only. Confirm VCP contractions, pivot, volume and risk manually.")
    with st.expander("Import aligned daily OHLCV histories", expanded=True):
        st.caption("Four CSVs: Date plus identical SYMBOL.NS columns; minimum 253 aligned sessions.")
        close=upload_frame("Close CSV","close")
        high=upload_frame("High CSV","high")
        low=upload_frame("Low CSV","low")
        volume=upload_frame("Volume CSV","volume")
        if all(x is not None for x in (close,high,low,volume)):
            try:
                coverage=setup_scanner_coverage(close,volume,high,low)
                st.json(coverage)
                candidates=compute_setup_scanner(close,volume,high_df=high,low_df=low)
                st.dataframe(candidates, use_container_width=True)
                st.download_button("Download VCP research candidates",candidates.to_csv(index=False),"edge_vcp_candidates.csv","text/csv")
            except (ValueError, KeyError) as exc:
                st.error(str(exc))
with tabs[3]:
    st.subheader("Portfolio & Journal")
    st.info("Research note preview only; no persistence and no Upstox orders.")
    with st.form("journal"):
        symbol=st.text_input("Symbol").strip().upper()
        note=st.text_area("Journal note")
        if st.form_submit_button("Preview"):
            if symbol and note.strip():
                st.write({"symbol":symbol,"note":note})
                st.caption("Not saved.")
            else:
                st.error("Symbol and note are required.")
st.caption("SPERA EDGE is not investment advice. No automatic execution, certified signals or return guarantees.")
