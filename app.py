"""SPERA EDGE: private, read-only research interface. No brokerage orders."""
import pandas as pd
import streamlit as st
from edge_core.analytics import stage2_template, market_breadth
from edge_core.momentum_v1 import apply_frozen_v1_scores
from edge_core.setup_scanner import compute_setup_scanner, setup_scanner_coverage
from edge_core.portfolio import position_size, journal_entry
from edge_core.portfolio_risk import risk_budget
from datetime import date
from pathlib import Path
import json
import hashlib

st.set_page_config(page_title="SPERA EDGE", page_icon="📈", layout="wide")
st.title("SPERA EDGE")
st.caption("Independent NIFTY 500 research • Automatic snapshots when available • No brokerage execution")

SNAPSHOT_DIR=Path(__file__).parent/"data"/"latest"
def snapshot_table(name):
    path=SNAPSHOT_DIR/f"{name}.csv"
    if not path.is_file():
        return None
    return pd.read_csv(path,index_col="Date",parse_dates=["Date"]).sort_index() if name in ("close","high","low","volume") else pd.read_csv(path)

try:
    edge_meta=json.loads((SNAPSHOT_DIR/"metadata.json").read_text())
    if edge_meta.get("universe")!="NIFTY_500" or edge_meta.get("certified") is not False or not (495 <= int(edge_meta.get("expected",0)) <= 505) or int(edge_meta.get("mapped",0))<495:
        raise ValueError("Unexpected snapshot contract")
except (OSError,ValueError,TypeError):
    edge_meta=None
if edge_meta:
    try:
        last_session=pd.Timestamp(edge_meta["last_session"]).date()
        age=(date.today()-last_session).days
        if age>5 or age<0:
            st.error(f"Snapshot is stale or dated in the future ({age} calendar days). Do not trade from these results.")
    except (ValueError,TypeError,KeyError):
        st.error("Snapshot session date invalid; research outputs are not certified.")
    st.caption(f'NIFTY 500 snapshot: {edge_meta["last_session"]} | Quality: {edge_meta["quality"]} | Research only')
else:
    st.warning("Automatic NIFTY 500 snapshot not yet published. The market-data pipeline is pending; no manual upload is required.")

tabs = st.tabs(["Market Pulse", "Leadership Scanner", "Trade Desk", "Portfolio & Journal"])
with tabs[0]:
    st.subheader("Market Pulse")
    prices = snapshot_table("close") if edge_meta else None

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
    st.caption("Automatically published research ranks are not certified trading signals.")
    ranks = snapshot_table("leadership") if edge_meta else None

    if ranks is not None:
        try:
            frame = ranks if isinstance(ranks,pd.DataFrame) else pd.read_csv(ranks)
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
                st.metric("Trusted PASS stocks", int(scored["Data_Quality"].eq("PASS").sum()))
                st.dataframe(scored.sort_values("Pure_Momentum_Rank").head(50), use_container_width=True)
                st.warning("Research ranks are provisional unless independently certified. REVIEW is not PASS.")
                st.download_button("Download ranked research CSV", scored.to_csv(index=False), "edge_ranked_research.csv", "text/csv")
                st.caption("Imported data is not independently certified. REVIEW/FAIL are not in the trusted list.")
        except Exception as exc:
            st.error(f"Unable to score input: {exc}")
    st.divider()
    st.subheader("SPERA Wisdom historical leadership (read-only import)")
    history_manifest=Path(__file__).parent/"data"/"history"/"manifest.json"
    if history_manifest.is_file():
        try:
            history_info=json.loads(history_manifest.read_text())
            history_weeks=history_info.get("weeks",[])
            if history_info.get("universe")!="NIFTY_500" or not history_weeks:
                raise ValueError("Unexpected history manifest")
            weeks=[row["weekly_key"] for row in history_weeks]
            selected_week=st.selectbox("Historical weekly snapshot",weeks,key="edge_history_week")
            record=next(row for row in history_weeks if row["weekly_key"]==selected_week)
            history_path=Path(__file__).parent/"data"/"history"/record["file"]
            digest=hashlib.sha256(history_path.read_bytes()).hexdigest()
            if digest!=record.get("sha256"):
                raise ValueError("Historical file checksum mismatch")
            historical=pd.read_csv(history_path)
            if len(historical)!=int(record["rows"]):
                raise ValueError("Historical file row count mismatch")
            st.caption(f"Historical snapshot: {selected_week} | {len(historical)} rows | Source: SPERA Wisdom trusted weekly snapshot. Not current trading signals.")
            if "Pure_Momentum_Rank" in historical.columns:
                historical=historical.sort_values("Pure_Momentum_Rank",na_position="last")
            st.dataframe(historical.head(50),use_container_width=True)
            st.download_button("Download selected historical week",historical.to_csv(index=False),f"edge_history_{selected_week}.csv","text/csv")
        except (OSError,ValueError,KeyError,pd.errors.ParserError) as exc:
            st.error(f"Historical snapshot unavailable: {exc}")
    else:
        st.info("No SPERA Wisdom historical snapshots imported yet; source D1 read access is required.")
    st.divider()
    stage_close=prices if edge_meta and prices is not None else None

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
    with st.container():
        st.caption("Automatic daily OHLCV snapshot; minimum 253 aligned sessions.")
        close=snapshot_table("close") if edge_meta else None
        high=snapshot_table("high") if edge_meta else None
        low=snapshot_table("low") if edge_meta else None
        volume=snapshot_table("volume") if edge_meta else None
        if not edge_meta:
            st.info("Waiting for the automated OHLCV snapshot. No manual upload required.")
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
    st.caption("Position planning and session-only journal. Export entries to retain them.")
    capital=st.number_input("Capital (INR)",min_value=1.0,value=500000.0)
    risk_pct=st.number_input("Risk per trade (%)",min_value=0.1,max_value=5.0,value=1.0)
    committed_risk=st.number_input("Existing open-position risk (INR)",min_value=0.0,value=0.0)
    entry=st.number_input("Entry",min_value=0.01,value=100.0)
    stop=st.number_input("Stop",min_value=0.01,value=95.0)
    try:
        budget=risk_budget(capital,risk_pct,committed_risk)
        sizing=position_size(capital,risk_pct,entry,stop)
        sizing["quantity"]=min(sizing["quantity"],int(budget["new_trade_budget"]//sizing["risk_per_share"]))
        sizing["planned_risk"]=sizing["quantity"]*sizing["risk_per_share"]
        sizing["notional"]=sizing["quantity"]*entry
        st.metric("Remaining portfolio risk capacity (INR)",round(budget["available_risk"],2))
        st.metric("Risk-based quantity",sizing["quantity"])
        st.metric("Planned stop loss (INR)",round(sizing["planned_risk"],2))
        if sizing["notional"]>capital:
            st.warning("Notional exposure exceeds capital.")
    except ValueError as exc:
        st.error(str(exc))
    if "journal_rows" not in st.session_state:
        st.session_state["journal_rows"]=[]
    with st.form("journal"):
        symbol=st.text_input("Symbol").strip().upper()
        side=st.selectbox("Side",["LONG","SHORT"])
        qty=st.number_input("Quantity",min_value=1,value=1,step=1)
        note=st.text_area("Journal note")
        if st.form_submit_button("Add to session journal"):
            try:
                st.session_state["journal_rows"].append(journal_entry(symbol,side,entry,stop,int(qty),note))
                st.success("Added to session. Export to save.")
            except ValueError as exc:
                st.error(str(exc))
    if st.session_state["journal_rows"]:
        journal=pd.DataFrame(st.session_state["journal_rows"])
        st.dataframe(journal,use_container_width=True)
        st.download_button("Export journal CSV",journal.to_csv(index=False),"spera_edge_journal.csv","text/csv")
        st.warning("Session only: persistent cloud storage not configured.")
st.caption("SPERA EDGE is not investment advice. No automatic execution, certified signals or return guarantees.")
