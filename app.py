"""SPERA EDGE: private, read-only research interface. No brokerage orders."""
import pandas as pd
import streamlit as st
from edge_core.analytics import stage2_template, market_breadth
from edge_core.breakout_health import breakout_health
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
from edge_exports import export_section, numbered
from edge_trader_readiness_ui import render_trader_readiness

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
        st.subheader("Breakout health (research-only)")
        st.caption("Prior 20-session high breakout on >=1.5x prior 50-session volume; "
                   "10-session forward close above breakout close without a stop breach = success. "
                   "Unresolved events are excluded. Heuristic, not SEPA certification.")
        breakout_high = snapshot_table("high")
        breakout_volume = snapshot_table("volume")
        if breakout_high is not None and breakout_volume is not None:
            health = breakout_health(prices, breakout_high, breakout_volume, low=snapshot_table('low'))
            m1, m2, m3 = st.columns(3)
            m1.metric("Qualified breakouts", health["qualified"])
            m2.metric("Resolved outcomes", health["resolved"])
            m3.metric("10-session success rate",
                      f'{health["success_rate_pct"]}%' if health["success_rate_pct"] is not None else "Insufficient outcomes")
            st.caption(f'Successes: {health["successes"]} | Failures: {health["failures"]} | '
                       f'Stop breaches: {health["stop_breaches"]} | Unresolved: {health["unresolved"]}. Current-universe survivorship bias applies.')
            st.dataframe(numbered(health["events"].tail(100)), use_container_width=True)
            export_section("Breakout outcomes", health["events"], "edge_breakout_outcomes")
        else:
            st.info("Breakout health requires aligned high, close and volume history.")
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
                st.dataframe(numbered(levels[levels["Research_Level"].ne("UNQUALIFIED")].sort_values("Pure_Momentum_Rank").head(50)),use_container_width=True)
                export_section("Leadership qualification", levels[levels["Research_Level"].ne("UNQUALIFIED")].sort_values("Pure_Momentum_Rank").head(50), "leadership_qualification")
                st.metric("Trusted PASS stocks", int(scored["Data_Quality"].eq("PASS").sum()))
                st.subheader("Trusted PASS research")
                st.dataframe(numbered(scored[scored["Data_Quality"].eq("PASS")].sort_values("Pure_Momentum_Rank").head(50)), use_container_width=True)
                export_section("Trusted PASS", scored[scored["Data_Quality"].eq("PASS")].sort_values("Pure_Momentum_Rank").head(50), "trusted_pass")
                st.subheader("Provisional REVIEW research")
                st.dataframe(numbered(scored[scored["Data_Quality"].eq("REVIEW")].sort_values("Pure_Momentum_Rank").head(50)), use_container_width=True)
                export_section("Provisional REVIEW", scored[scored["Data_Quality"].eq("REVIEW")].sort_values("Pure_Momentum_Rank").head(50), "provisional_review")
                st.subheader("Excluded FAIL records")
                st.dataframe(numbered(scored[scored["Data_Quality"].eq("FAIL")]), use_container_width=True)
                export_section("Excluded FAIL", scored[scored["Data_Quality"].eq("FAIL")], "excluded_fail")
                st.warning("Research ranks are provisional unless independently certified. REVIEW is not PASS.")
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
                            st.dataframe(numbered(sector_now),use_container_width=True)
                            export_section("Current sector research", sector_now, "current_sector_research")
                            st.download_button("Download provisional current sector research",sector_now.to_csv(index=False),"edge_current_sector_research.csv","text/csv")
                        except ValueError as sector_error:
                            st.warning(f"Current sector research unavailable: {sector_error}")
                    st.subheader("Archived sector leadership")
                    st.caption("Historical SPERA Wisdom sector rankings only; not a current EDGE sector signal.")
                    st.dataframe(numbered(archived_sectors.sort_values("sector_rank")),use_container_width=True)
                    export_section("Archived sectors", archived_sectors.sort_values("sector_rank"), "archived_sectors_"+selected_week)
                    st.caption(f"Sector coverage: {len(archived_cohorts)} historical stock records; not a complete live classification.")

                else:
                    st.warning("Archived sector evidence failed identity or date validation.")

            if "Pure_Momentum_Rank" in historical.columns:
                historical=historical.sort_values("Pure_Momentum_Rank",na_position="last")
            st.dataframe(numbered(historical.head(50)),use_container_width=True)
            export_section("Historical weekly leadership", historical, "history_"+selected_week)
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
        st.dataframe(numbered(pd.DataFrame(records)), use_container_width=True)
        export_section("Price template diagnostics", pd.DataFrame(records), "price_template")
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
                st.dataframe(numbered(candidates), use_container_width=True)
                export_section("VCP research candidates", candidates, "vcp_candidates")
                membership_file = SNAPSHOT_DIR / "current_membership.csv"
                provenance_file = SNAPSHOT_DIR / "evidence.json"
                leadership_frame = snapshot_table("leadership")
                if membership_file.is_file() and provenance_file.is_file() and leadership_frame is not None:
                    provenance = json.loads(provenance_file.read_text())
                    if provenance.get("membership_sha256") == hashlib.sha256(membership_file.read_bytes()).hexdigest() and provenance.get("membership_source"):
                        members = pd.read_csv(membership_file, dtype={"ISIN Code": str})
                        period = st.date_input("Financial evidence period end", key="trade_readiness_period")
                        render_trader_readiness(leadership_frame, members, candidates, period.isoformat(), snapshot_fresh=snapshot_usable)
                    else:
                        st.warning("Trading readiness requires verified membership provenance.")

            except (ValueError, KeyError) as exc:
                st.error(str(exc))
with tabs[3]:
    st.subheader("Portfolio & Journal")
    render_private_portfolio(prices,snapshot_usable)
with tabs[4]:
    st.caption("Owner-only financial intake. Research records are not certified.")
    membership_path = SNAPSHOT_DIR / "current_membership.csv"
    if not edge_meta or not snapshot_usable or not membership_path.is_file():
        st.warning("Fresh validated snapshot and official membership with ISIN identities required.")
    else:
        try:
            membership = pd.read_csv(membership_path, dtype={"ISIN Code": str})
            evidence_path = SNAPSHOT_DIR / "evidence.json"
            if not evidence_path.is_file():
                raise ValueError("Official membership provenance missing")
            provenance = json.loads(evidence_path.read_text())
            membership_hash = hashlib.sha256(membership_path.read_bytes()).hexdigest()
            if provenance.get("membership_sha256") != membership_hash or not provenance.get("membership_source"):
                raise ValueError("Official membership provenance/hash mismatch")
            ranks = snapshot_table("leadership")
            if ranks is None:
                st.warning("No leadership ranks available for evidence review.")
            else:
                scored = apply_frozen_v1_scores(ranks.copy())
                financial_path = SNAPSHOT_DIR / "financial_records.csv"
                financial_records = pd.read_csv(financial_path).to_dict("records") if financial_path.is_file() else []
                st.warning("Select the reporting period end from the original company filings. No date is inferred.")
                period_end = st.date_input("Financial reporting period end", key="edge_financial_period_end")
                if st.checkbox("Open owner-only evidence intake", value=False):
                    render_financial_evidence_review(scored, membership, financial_records, period_end.isoformat())
        except (ValueError, KeyError, OSError, pd.errors.ParserError) as exc:
            st.error("Financial evidence review unavailable: " + str(exc))
st.caption("SPERA EDGE is not investment advice. No automatic execution, certified signals or return guarantees.")
