"""SPERA EDGE: private, read-only research interface. No brokerage orders."""
import pandas as pd
import streamlit as st
from edge_core.analytics import stage2_template, market_breadth
from edge_core.momentum_v1 import apply_frozen_v1_scores
from edge_core.setup_scanner import compute_setup_scanner, setup_scanner_coverage
from edge_core.portfolio import position_size, journal_entry
from edge_core.portfolio_risk import risk_budget
from edge_core.leadership_levels import classify_leadership
from edge_core.relative_strength import cross_sectional_rs
from edge_core.current_sectors import current_sector_research
from datetime import date
from pathlib import Path
import json
import hashlib
from datetime import datetime
from zoneinfo import ZoneInfo
from edge_core.snapshot_integrity import validate_snapshot
from edge_workspace import render_market, render_entries, render_private_portfolio, leadership_evidence, render_industries
from edge_financial_review import render_financial_evidence_review

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
    validate_snapshot(SNAPSHOT_DIR)
    edge_meta=json.loads((SNAPSHOT_DIR/"metadata.json").read_text())
    if edge_meta.get("universe")!="NIFTY_500" or edge_meta.get("certified") is not False or not (495 <= int(edge_meta.get("expected",0)) <= 505) or int(edge_meta.get("mapped",0))<495:
        raise ValueError("Unexpected snapshot contract")
except (OSError,ValueError,TypeError,KeyError):
    edge_meta=None
snapshot_usable=False
if edge_meta:
    try:
        last_session=pd.Timestamp(edge_meta["last_session"]).date()
        now_ist=datetime.now(ZoneInfo("Asia/Kolkata"))
        age=(now_ist.date()-last_session).days
        snapshot_usable=0 <= age <= 5 and (age > 0 or now_ist.hour >= 16)
        if age>5 or age<0:
            st.error(f"Snapshot is stale or dated in the future ({age} calendar days). Do not trade from these results.")
    except (ValueError,TypeError,KeyError):
        st.error("Snapshot session date invalid; research outputs are not certified.")
    st.caption(f'NIFTY 500 snapshot: {edge_meta["last_session"]} | Quality: {edge_meta["quality"]} | Research only')
else:
    st.warning("Automatic NIFTY 500 snapshot not yet published. The market-data pipeline is pending; no manual upload is required.")

tabs = st.tabs(["Market Pulse", "Leadership Scanner", "Trade Desk", "Portfolio & Journal", "Financial Evidence Review"])
with tabs[0]:
    st.subheader("Market Pulse")
    prices = snapshot_table("close") if edge_meta else None

    if prices is not None:
        render_market(prices)
        render_industries(SNAPSHOT_DIR,prices)
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
                # Research levels remain provisional until RS, sector and source gates are verified.
                close_for_levels=snapshot_table("close") if edge_meta else None
                # Evaluate setup diagnostics only for high-percentile candidates.
                # These remain research-only until source and RS gates are certified.
                candidate_symbols=scored.loc[
                    pd.to_numeric(scored["Percentile"],errors="coerce").ge(80)
                    & scored["Data_Quality"].isin(["PASS","REVIEW"]), "Symbol"
                ].dropna().astype(str).tolist()
                setup_candidates=None
                if candidate_symbols and close_for_levels is not None:
                    hi=snapshot_table("high")
                    lo=snapshot_table("low")
                    vol=snapshot_table("volume")
                    if all(x is not None for x in (hi,lo,vol)):
                        setup_candidates=compute_setup_scanner(
                            close_for_levels,vol,symbols=candidate_symbols,
                            high_df=hi,low_df=lo
                        )
                levels=classify_leadership(scored,close_for_levels,setups=setup_candidates)
                if close_for_levels is not None:
                    rs_table=cross_sectional_rs(close_for_levels)
                    levels=levels.merge(rs_table,on="Symbol",how="left",validate="one_to_one")
                    levels["RS_80th_Percentile_Diagnostic"]=pd.to_numeric(
                        levels["RS_Universe_252D_Pctile"],errors="coerce"
                    ).ge(80)
                else:
                    levels["RS_80th_Percentile_Diagnostic"]=False
                # This is a price-only research confluence, not SEPA certification.
                levels["SEPA_Technical_Research"]=(
                    levels["Price_Template_Pass"]
                    & levels["RS_80th_Percentile_Diagnostic"]
                    & levels["Data_Quality"].isin(["REVIEW","PASS"])
                )
                levels["SEPA_Certified"]=False
                levels=leadership_evidence(levels,close_for_levels,SNAPSHOT_DIR)
                st.caption("Technical confluence = price template + NIFTY 500 price-strength percentile. It excludes earnings, verified benchmark RS and current sector certification.")
                st.subheader("Leadership qualification funnel")
                a1,a2,a3=st.columns(3)
                a1.metric("Momentum leaders (trusted)",int(levels["Momentum_Leader"].sum()))
                a2.metric("Provisional + price template",int((levels["Provisional_Momentum_Candidate"] & levels["Price_Template_Pass"]).sum()))
                a3.metric("Provisional momentum candidates",int(levels["Provisional_Momentum_Candidate"].sum()))
                st.metric("Provisional setup reviews",int(levels["Research_Level"].eq("PROVISIONAL_SETUP_REVIEW").sum()))
                st.metric("RS percentile ≥80 (research only)",int(levels["RS_80th_Percentile_Diagnostic"].sum()))
                st.caption("Setup checks use actual OHLCV and remain provisional. No certified SEPA signals.")
                st.caption("SEPA and actionable setup qualification pending independent relative strength, sector and source checks.")
                st.dataframe(levels[levels["Research_Level"].ne("UNQUALIFIED")].sort_values("Pure_Momentum_Rank").head(50),use_container_width=True)
                st.metric("Trusted PASS stocks", int(scored["Data_Quality"].eq("PASS").sum()))
                st.subheader("Trusted PASS research")
                st.dataframe(scored[scored["Data_Quality"].eq("PASS")].sort_values("Pure_Momentum_Rank").head(50), use_container_width=True)
                st.subheader("Provisional REVIEW research")
                st.dataframe(scored[scored["Data_Quality"].eq("REVIEW")].sort_values("Pure_Momentum_Rank").head(50), use_container_width=True)
                st.subheader("Excluded FAIL records")
                st.dataframe(scored[scored["Data_Quality"].eq("FAIL")], use_container_width=True)
                st.download_button("Download qualification evidence",levels.to_csv(index=False),"edge_qualification_evidence.csv","text/csv")
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
            sector_path=history_path.parent/f"nifty500_{selected_week}_sectors.csv"
            cohort_path=history_path.parent/f"nifty500_{selected_week}_cohorts.csv"
            if sector_path.is_file() and cohort_path.is_file():
                archived_sectors=pd.read_csv(sector_path)
                archived_cohorts=pd.read_csv(cohort_path)
                if (len(archived_sectors)==int(record["sector_rows"])
                    and len(archived_cohorts)==int(record["cohort_rows"])
                    and archived_sectors["weekly_key"].eq(selected_week).all()
                    and archived_cohorts["week_key"].eq(selected_week).all()
                    and not archived_sectors["sector"].duplicated().any()
                    and not archived_cohorts["ticker"].duplicated().any()):
                    current_prices=snapshot_table("close") if edge_meta else None
                    if current_prices is not None:
                        try:
                            sector_now=current_sector_research(current_prices,archived_cohorts,selected_week)
                            st.subheader("Current price-based sector momentum")
                            st.caption("Live price returns grouped using archived sector membership from "+selected_week+". PROVISIONAL; mapping is incomplete and not a current certified sector index.")
                            st.dataframe(sector_now,use_container_width=True)
                            st.download_button("Download provisional current sector research",sector_now.to_csv(index=False),"edge_current_sector_research.csv","text/csv")
                        except ValueError as sector_error:
                            st.warning(f"Current sector research unavailable: {sector_error}")
                    st.subheader("Archived sector leadership")
                    st.caption("Historical SPERA Wisdom sector rankings only; not a current EDGE sector signal.")
                    st.dataframe(archived_sectors.sort_values("sector_rank"),use_container_width=True)
                    st.download_button(
                        "Download archived sector rankings",
                        archived_sectors.sort_values("sector_rank").to_csv(index=False),
                        f"edge_archived_sectors_{selected_week}.csv","text/csv"
                    )
                    st.caption(f"Sector coverage: {len(archived_cohorts)} historical stock records; not a complete live classification.")

                else:
                    st.warning("Archived sector evidence failed identity or date validation.")

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
                if snapshot_usable:
                    render_entries(close,high,low,volume,edge_meta["last_session"])
                else:
                    st.error("Entry planning disabled: snapshot is stale, future-dated or not from a completed session.")
                coverage=setup_scanner_coverage(close,volume,high,low)
                st.json(coverage)
                candidates=compute_setup_scanner(close,volume,high_df=high,low_df=low)
                st.dataframe(candidates, use_container_width=True)
                st.download_button("Download VCP research candidates",candidates.to_csv(index=False),"edge_vcp_candidates.csv","text/csv")
            except (ValueError, KeyError) as exc:
                st.error(str(exc))
with tabs[3]:
    st.subheader("Portfolio & Journal")
    render_private_portfolio(prices,snapshot_usable)
st.caption("SPERA EDGE is not investment advice. No automatic execution, certified signals or return guarantees.")

with tabs[4]:
    st.caption("Owner-only financial evidence intake; records are not independently verified.")
    membership_path = SNAPSHOT_DIR / "current_membership.csv"
    ranks_for_review = snapshot_table("leadership") if edge_meta else None
    if ranks_for_review is None or not membership_path.is_file():
        st.warning("Verified leadership and official membership evidence files are required.")
    else:
        try:
            membership_for_review = pd.read_csv(membership_path)
            if not {"Symbol", "ISIN Code"}.issubset(membership_for_review.columns):
                st.warning("Membership ISIN identity evidence is not yet published. Review locked.")
            else:
                st.warning("Financial acquisition feed not connected: intake requests are provisional and must not imply a source was checked.")
                reporting_period = st.date_input("Reporting period end for manual review", value=date(2026, 9, 30), key="financial_review_period")
                scored_for_review = apply_frozen_v1_scores(ranks_for_review)
                render_financial_evidence_review(scored_for_review, membership_for_review, [], reporting_period.isoformat())
        except (ValueError, KeyError, OSError, pd.errors.ParserError) as exc:
            st.error("Financial evidence review unavailable: " + str(exc))
