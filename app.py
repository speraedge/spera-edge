"""SPERA EDGE: private, read-only research interface. No brokerage orders."""
import pandas as pd
import streamlit as st
from edge_core.analytics import stage2_template, market_breadth
from edge_core.breakout_health import breakout_health, breakout_horizon_comparison
from edge_core.breadth_breakout_bridge import breadth_breakout_summary
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
from edge_core.research_fallback import load_leadership
from edge_core.snapshot_integrity import validate_snapshot
from edge_core.ohlcv_integrity import snapshot_is_fresh
from edge_workspace import render_market, render_entries, render_private_portfolio, leadership_evidence, render_industries, market_report, resolve_owner
from edge_exports import export_section, numbered
from edge_trader_readiness_ui import render_trader_readiness

@st.cache_data(show_spinner=False, ttl=3600)
def cached_v1(snapshot_identity, _frame):
    return apply_frozen_v1_scores(_frame)

@st.cache_data(show_spinner=False, ttl=3600)
def cached_setups(snapshot_identity, _close, _volume, _high, _low, symbols=None):
    return compute_setup_scanner(_close, _volume, symbols=symbols, high_df=_high, low_df=_low)

@st.cache_data(show_spinner=False, ttl=3600)
def cached_breakout_health(snapshot_identity, _close, _high, _volume, _low):
    return breakout_health(_close, _high, _volume, low=_low)

@st.cache_data(show_spinner=False, ttl=3600)
def cached_stage2_diagnostics(snapshot_identity, _close):
    records = []
    for sym in _close:
        res = stage2_template(_close[sym])
        records.append({"Symbol": sym, "Price-template pass": res["eligible"], "Note": res["reason"]})
    return pd.DataFrame(records)

@st.cache_data(show_spinner=False, ttl=3600, max_entries=100)
def cached_symbol_chart(snapshot_identity, symbol, _open_frame, _high, _low, _close, _volume, pivot=None, stop=None):
    from edge_symbol_charts import render_validated_ohlcv_png
    return render_validated_ohlcv_png(_open_frame, _high, _low, _close, _volume, symbol,
                                     pivot=pivot, stop=stop)

st.set_page_config(page_title="SPERA EDGE", page_icon="📈", layout="wide")
st.title("SPERA EDGE")
st.caption("Independent NIFTY 500 research • Automatic snapshots when available • No brokerage execution")

data_source = st.radio("Data Source", ["Verified EOD", "Provisional Evening"], horizontal=True, key="edge_data_source")
is_provisional = data_source == "Provisional Evening"
SNAPSHOT_DIR = Path(__file__).parent / "data" / ("provisional" if is_provisional else "latest")
if is_provisional:
    st.warning("Warning: Provisional data. Do not execute trades based on this. Position Sizing and Journal are locked.")
def snapshot_identity():
    metadata = SNAPSHOT_DIR / 'metadata.json'
    return hashlib.sha256(metadata.read_bytes()).hexdigest() if metadata.is_file() else 'MISSING_METADATA'

def snapshot_table(name):
    path=SNAPSHOT_DIR/f"{name}.csv"
    if not path.is_file():
        return None
    return pd.read_csv(path,index_col="Date",parse_dates=["Date"]).sort_index() if name in ("open","close","high","low","volume") else pd.read_csv(path)

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
        snapshot_usable=(not is_provisional) and snapshot_is_fresh(last_session, now_ist)
        if not snapshot_usable:
            st.info(f"Note: Displaying research data from {last_session.isoformat()}. Execution forms are locked until fresh price data is available.")
    except (ValueError,TypeError,KeyError):
        st.info(f"Note: Displaying research data from {edge_meta.get('last_session', 'unknown session')}. Execution forms are locked until fresh price data is available.")
    st.caption(f'NIFTY 500 snapshot: {edge_meta["last_session"]} | Quality: {edge_meta["quality"]} | Research only')
else:
    st.warning("Automatic NIFTY 500 snapshot not yet published. The market-data pipeline is pending; no manual upload is required.")

page = st.sidebar.radio("SPERA EDGE navigation", ["Market Pulse", "Leadership Scanner", "Trade Desk", "Portfolio & Journal", "Financial Evidence Review"], key="edge_active_page")
prices = snapshot_table("close") if edge_meta and page in ("Market Pulse", "Portfolio & Journal") else None
if page == "Market Pulse":
    st.subheader("Market Pulse")
    if prices is not None:
        render_market(prices)
        st.subheader("Breakout health (research-only)")
        st.caption("Prior 20-session high breakout on >=1.5x prior 50-session volume; "
                   "10-session forward close above breakout close without a stop breach = success. "
                   "Unresolved events are excluded. Heuristic, not SEPA certification.")
        breakout_high = snapshot_table("high")
        breakout_volume = snapshot_table("volume")
        if breakout_high is not None and breakout_volume is not None:
            health = cached_breakout_health(snapshot_identity(), prices, breakout_high, breakout_volume, snapshot_table('low'))
            low_history = snapshot_table("low")
            if low_history is not None:
                horizon_summary = breakout_horizon_comparison(
                    prices, breakout_high, breakout_volume, low=low_history)
                st.subheader("5 / 10 / 20-session outcome comparison")
                st.caption("Each horizon has a separate cooldown and may represent a different "
                           "event cohort; compare rates cautiously. Stop breaches use daily lows, "
                           "not executable stop fills.")
                st.dataframe(numbered(horizon_summary), use_container_width=True)
                export_section("Breakout horizon comparison", horizon_summary, "edge_breakout_horizons")
                with st.expander("Historical OHLCV rule replay (research only)", expanded=False):
                    st.caption("Uses the existing saved Upstox OHLCV snapshot; no new API request. "
                               "Signal-day inputs exclude future candles. Current-universe and "
                               "corporate-action limitations prevent certified return claims.")
                    available_sessions = prices.index
                    default_start = available_sessions[max(0, len(available_sessions) - 252)].date()
                    replay_start = st.date_input("Replay from", value=default_start,
                                                 min_value=available_sessions[0].date(),
                                                 max_value=available_sessions[-1].date(),
                                                 key="edge_replay_start")
                    replay_end = st.date_input("Replay through", value=available_sessions[-1].date(),
                                               min_value=available_sessions[0].date(),
                                               max_value=available_sessions[-1].date(),
                                               key="edge_replay_end")
                    if st.button("Run historical rule replay", key="edge_run_replay"):
                        from edge_core.historical_replay import replay_breakout_rules
                        if replay_start > replay_end:
                            st.error("Replay start must not exceed end.")
                        else:
                            with st.spinner("Evaluating historical breakout rules..."):
                                replay = replay_breakout_rules(
                                    prices, breakout_high, low_history, breakout_volume,
                                    start=replay_start, end=replay_end)
                            st.session_state["edge_replay_result"] = replay
                            st.session_state["edge_replay_range"] = (str(replay_start), str(replay_end))
                    replay = st.session_state.get("edge_replay_result")
                    if replay is not None:
                        st.caption("Last replay period: " + str(st.session_state.get("edge_replay_range", "unknown")))
                        resolved = replay["Outcome"].isin(["SUCCESS", "FAILURE", "STOP_BREACH"])
                        wins = int((replay["Outcome"] == "SUCCESS").sum())
                        total = int(resolved.sum())
                        st.caption(f"Signals: {len(replay)} | Resolved: {total} | "
                                   f"Successes: {wins} | Stop breaches: "
                                   f"{int((replay['Outcome'] == 'STOP_BREACH').sum())} | "
                                   f"Unresolved: {len(replay)-total}. "
                                   "This is an outcome study, not a net-return backtest.")
                        st.dataframe(numbered(replay.tail(250)), use_container_width=True)
                        export_section("Historical rule replay", replay, "edge_historical_rule_replay")

            m1, m2, m3 = st.columns(3)
            m1.metric("Qualified breakouts", health["qualified"])
            m2.metric("Resolved outcomes", health["resolved"])
            m3.metric("10-session success rate",
                      f'{health["success_rate_pct"]}%' if health["success_rate_pct"] is not None else "Insufficient outcomes")
            st.caption(f'Successes: {health["successes"]} | Failures: {health["failures"]} | '
                       f'Stop breaches: {health["stop_breaches"]} | Unresolved: {health["unresolved"]}. Current-universe survivorship bias applies.')
            st.dataframe(numbered(health["events"].tail(100)), use_container_width=True)
            export_section("Breakout outcomes", health["events"], "edge_breakout_outcomes")
            breadth_history = market_report(prices)["history"]
            breadth_history.attrs["universe_size"] = len(prices.columns)
            breadth_groups = breadth_breakout_summary(health["events"], breadth_history)
            st.subheader("Breakout outcomes by market breadth")
            st.caption("Same-session breadth; current-universe survivorship bias. "
                       "No breadth evidence is kept separate. Research-only.")
            st.dataframe(numbered(breadth_groups), use_container_width=True)
            export_section("Breadth breakout outcomes", breadth_groups, "edge_breadth_breakout_outcomes")
            history_root = Path(__file__).parent / "data" / "history"
            if (history_root / "manifest.json").is_file() and not health["events"].empty:
                try:
                    from edge_core.historical_leadership_bridge import historical_leadership_context, leadership_breakout_summary
                    linked = historical_leadership_context(health["events"], history_root)
                    st.subheader("Breakouts vs earlier SperaWisdom leadership")
                    st.caption("Strictly prior weekly rank only; missing history stays missing. "
                               "Historical Wisdom research is read-only, not an EDGE trading certification.")
                    grouped = leadership_breakout_summary(linked)
                    st.caption("Historical outcome groups use strictly earlier weekly rankings. "
                               "Missing ranks and unresolved outcomes are never counted as failures.")
                    st.dataframe(numbered(grouped), use_container_width=True)
                    export_section("Leadership breakout comparison", grouped, "edge_leadership_breakout_summary")
                    st.dataframe(numbered(linked.tail(100)), use_container_width=True)
                    export_section("Breakouts with prior leadership", linked, "edge_breakout_leadership")
                except (OSError, ValueError, KeyError, pd.errors.ParserError) as exc:
                    st.warning(f"Historical leadership comparison unavailable: {exc}")
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
elif page == "Leadership Scanner":
    st.subheader("Leadership Scanner")
    st.caption("Automatically published research ranks are not certified trading signals.")
    ranks, leadership_date, leadership_historical = load_leadership(
        SNAPSHOT_DIR, Path(__file__).parent / "data" / "history",
        latest_date=edge_meta.get("last_session") if edge_meta else None)
    if ranks is not None:
        st.info(f"Displaying leadership data from {leadership_date}" + (" — historical fallback; not current trading signals" if leadership_historical else " — current research snapshot"))

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
                scored=cached_v1(snapshot_identity(), frame)
                # Research levels remain provisional until RS, sector and source gates are verified.
                close_for_levels=snapshot_table("close") if edge_meta else None
                # Scan the complete validated OHLCV universe. Momentum rank is not
                # a prefilter for technical setups; certification remains unchanged.
                setup_candidates=None
                if close_for_levels is not None:
                    hi=snapshot_table("high")
                    lo=snapshot_table("low")
                    vol=snapshot_table("volume")
                    if all(x is not None for x in (hi,lo,vol)):
                        setup_candidates=cached_setups(snapshot_identity(), close_for_levels, vol, hi, lo)
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
                st.subheader("Technical Confluence Watchlist — research only")
                rs_70 = pd.to_numeric(levels["RS_Universe_252D_Pctile"], errors="coerce").ge(70)
                template_pass = levels["Price_Template_Pass"].fillna(False)
                setup_pass = levels["Setup_Diagnostic"].fillna(False)
                c1, c2, c3, c4 = st.columns(4)
                c1.metric("RS ≥70", int(rs_70.sum()))
                c2.metric("Price Template Pass", int(template_pass.sum()))
                c3.metric("VCP Setup Pass", int(setup_pass.sum()))
                confluence = levels.loc[rs_70 & template_pass & setup_pass].sort_values("Pure_Momentum_Rank")
                c4.metric("All three gates", len(confluence))
                st.caption("Full-universe technical intersection, not a certified SEPA or trading signal. RS is cross-sectional price performance, not benchmark-relative RS.")
                st.dataframe(numbered(confluence), use_container_width=True)
                export_section("Technical Confluence Watchlist", confluence, "technical_confluence_watchlist")
                st.subheader("Leadership qualification funnel")
                a1,a2,a3=st.columns(3)
                a1.metric("Momentum leaders (trusted)",int(levels["Momentum_Leader"].sum()))
                a2.metric("Provisional + price template",int((levels["Provisional_Momentum_Candidate"] & levels["Price_Template_Pass"]).sum()))
                a3.metric("Provisional momentum candidates",int(levels["Provisional_Momentum_Candidate"].sum()))
                st.metric("Provisional setup reviews",int(levels["Research_Level"].eq("PROVISIONAL_SETUP_REVIEW").sum()))
                st.metric("RS percentile ≥80 (research only)",int(levels["RS_80th_Percentile_Diagnostic"].sum()))
                st.caption("Setup checks use actual OHLCV and remain provisional. No certified SEPA signals.")
                st.caption("SEPA and actionable setup qualification pending independent relative strength, sector and source checks.")
                st.dataframe(numbered(levels[levels["Research_Level"].ne("UNQUALIFIED")].sort_values("Pure_Momentum_Rank")),use_container_width=True)
                export_section("Leadership qualification", levels[levels["Research_Level"].ne("UNQUALIFIED")].sort_values("Pure_Momentum_Rank"), "leadership_qualification")
                st.metric("Trusted PASS stocks", int(scored["Data_Quality"].eq("PASS").sum()))
                st.subheader("Trusted PASS research")
                st.dataframe(numbered(scored[scored["Data_Quality"].eq("PASS")].sort_values("Pure_Momentum_Rank").head(50)), use_container_width=True)
                export_section("Trusted PASS", scored[scored["Data_Quality"].eq("PASS")].sort_values("Pure_Momentum_Rank").head(50), "trusted_pass")
                st.subheader("Provisional REVIEW research")
                st.dataframe(numbered(scored[scored["Data_Quality"].eq("REVIEW")].sort_values("Pure_Momentum_Rank")), use_container_width=True)
                export_section("Provisional REVIEW", scored[scored["Data_Quality"].eq("REVIEW")].sort_values("Pure_Momentum_Rank"), "provisional_review")
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
        stage2_records = cached_stage2_diagnostics(snapshot_identity(), stage_close)
        st.dataframe(numbered(stage2_records), use_container_width=True)
        export_section("Price template diagnostics", stage2_records, "price_template")
        st.caption("Stage 2 relative-strength requirement must be verified separately. Price-only pass is not full Stage 2 qualification.")
elif page == "Trade Desk":
    if is_provisional:
        st.info("Provisional Trade Desk is read-only. Fundamentals intake, saved-plan updates and D1 writes are disabled.")
    else:
        from edge_fundamentals_ui import render_fundamentals
        render_fundamentals(SNAPSHOT_DIR)
        st.subheader("Trade Desk")
        from edge_core.saved_trade_plans import OwnerPlanStore, evaluate_plans, status
        from edge_core.d1_store import d1_query
        st.subheader("Saved Trade Plans")
        st.caption("Private D1-backed research plans. Login required. Invalidated plans are retained in owner-scoped D1 audit history.")
        desk_close = snapshot_table("close") if edge_meta else None
        last_prices = desk_close.iloc[-1].to_dict() if desk_close is not None and not desk_close.empty else {}
        plan_store = None
        try:
            owner, owner_status = resolve_owner(st)
            if owner_status == "CONFIGURATION_REQUIRED":
                st.warning("Saved plans locked: owner authentication not configured.")
            elif owner_status == "LOGIN_REQUIRED":
                if st.button("Sign in to saved plans", key="plans_sign_in"):
                    st.login()
            elif owner_status == "UNAUTHORIZED":
                raise ValueError("A verified, allowlisted OIDC identity is required")
            else:
                keys = ("EDGE_CF_ACCOUNT_ID", "EDGE_D1_DATABASE_ID", "EDGE_CF_API_TOKEN")
                creds = [st.secrets.get(k) for k in keys]
                if not all(creds):
                    raise ValueError("D1 credentials missing")
                def plan_query(sql, params=()):
                    return d1_query(sql, params, account_id=creds[0], database_id=creds[1], token=creds[2])
                plan_store = OwnerPlanStore(owner, plan_query)
                plan_store.initialize()
        except (ValueError, KeyError, TypeError, RuntimeError) as exc:
            st.warning(f"Private saved plans unavailable: {exc}")
        if plan_store is not None:
            try:
                saved = plan_store.list_active()
                for plan in saved:
                    if status(plan, last_prices.get(plan["Symbol"])) == "INVALID":
                        plan_store.invalidate(plan["plan_id"])
                active = plan_store.list_active()
                evaluated = evaluate_plans(active, last_prices)
                if evaluated:
                    st.dataframe(pd.DataFrame(evaluated), use_container_width=True, hide_index=True)
                    for i, plan in enumerate(evaluated):
                        cols = st.columns([3, 1, 1])
                        cols[0].write(f"{plan['Symbol']} · {plan['Setup Date']} · {plan['Status']}")
                        if cols[1].button("Load Plan", key=f"load_plan_{i}"):
                            st.session_state["saved_plan_selected"] = plan_store.load_active(plan["plan_id"])
                            st.rerun()
                        if plan["Status"] == "TRIGGERED":
                            if cols[2].button("Calculate Size", key=f"size_plan_{i}", disabled=not snapshot_usable):
                                st.session_state["saved_plan_selected"] = plan_store.load_active(plan["plan_id"])
                                st.session_state["saved_plan_size_requested"] = True
                                st.rerun()
                else:
                    st.info("No active saved plans.")
                selected_plan = st.session_state.get("saved_plan_selected")
                if selected_plan:
                    # Recheck ownership and ACTIVE status every rerun; never trust session state as authority.
                    try:
                        selected_plan = plan_store.load_active(selected_plan["plan_id"])
                        st.session_state["saved_plan_selected"] = selected_plan
                        st.write({"Loaded research plan": selected_plan})
                        if st.session_state.pop("saved_plan_size_requested", False):
                            st.info("Review the loaded entry and stop in Portfolio & Journal. Sizing remains locked when the snapshot is stale.")
                    except (KeyError, ValueError):
                        st.session_state.pop("saved_plan_selected", None)
                with st.form("save_trade_plan"):
                    plan_symbol = st.text_input("Plan symbol", key="plan_symbol")
                    plan_pivot = st.number_input("Pivot / entry", min_value=0.01, value=100.0, key="plan_pivot")
                    plan_stop = st.number_input("Initial stop", min_value=0.01, value=95.0, key="plan_stop")
                    plan_target = st.number_input("Target", min_value=0.01, value=115.0, key="plan_target")
                    plan_date = st.date_input("Setup date", key="plan_date")
                    plan_submit = st.form_submit_button("Save Plan")
                if plan_submit:
                    plan_store.add({"Symbol": plan_symbol, "Pivot": plan_pivot, "Stop": plan_stop,
                                    "Target": plan_target, "Setup Date": plan_date.isoformat()})
                    st.success("Private plan saved to D1.")
                    st.rerun()
            except (ValueError, KeyError, TypeError, RuntimeError) as exc:
                st.warning(f"Saved plans unavailable: {exc}")
    trade_ranks, trade_rank_date, trade_historical = load_leadership(
        SNAPSHOT_DIR, Path(__file__).parent / "data" / "history",
        latest_date=edge_meta.get("last_session") if edge_meta else None)
    if trade_ranks is not None:
        st.info(f"Momentum / RS research from {trade_rank_date}" + (" (historical fallback)" if trade_historical else ""))
        rank_cols = [c for c in ("Symbol", "Percentile", "Pure_Momentum_Rank", "Data_Quality", "Ret_6M", "Ret_12M") if c in trade_ranks.columns]
        st.dataframe(trade_ranks[rank_cols].sort_values("Pure_Momentum_Rank", na_position="last"), use_container_width=True, hide_index=True)
    else:
        st.info("Leadership / RS research unavailable: no validated latest or historical archive.")
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
                render_entries(close,high,low,volume,edge_meta["last_session"], leadership=trade_ranks, leadership_date=trade_rank_date, leadership_historical=trade_historical, data_source='provisional' if is_provisional else 'verified')
                coverage=setup_scanner_coverage(close,volume,high,low)
                st.json(coverage)
                candidates=cached_setups(snapshot_identity(), close, volume, high, low)
                st.dataframe(numbered(candidates), use_container_width=True)
                export_section("VCP research candidates", candidates, "vcp_candidates")
                with st.expander("Candlestick chart · saved OHLCV research", expanded=False):
                    open_frame = snapshot_table("open")
                    if open_frame is None:
                        st.warning("Actual opening prices are not yet published. Candlestick charts unavailable.")
                    else:
                        symbols = sorted(set(close.columns) & set(high.columns) &
                                         set(low.columns) & set(volume.columns) & set(open_frame.columns))
                        selected = st.selectbox("Chart symbol", symbols, key="edge_chart_symbol")
                        if selected:
                            # Levels are sourced only from existing entry diagnostics.
                            from edge_workspace import entry_diagnostics
                            levels = entry_diagnostics(close, high, low, volume, edge_meta["last_session"])
                            matched = levels.loc[levels["Symbol"].eq(selected)] if "Symbol" in levels else levels.iloc[0:0]
                            pivot = float(matched.iloc[0]["Pivot"]) if not matched.empty and pd.notna(matched.iloc[0]["Pivot"]) else None
                            stop = float(matched.iloc[0]["Stop"]) if not matched.empty and pd.notna(matched.iloc[0]["Stop"]) else None
                            try:
                                # Explain missing OHLCV sessions rather than silently discarding them.
                                chart_indexes = []
                                for chart_frame in (open_frame, high, low, close, volume):
                                    chart_series = pd.to_numeric(chart_frame[selected], errors="coerce")
                                    chart_indexes.append(pd.DatetimeIndex(pd.to_datetime(chart_series.dropna().index)))
                                aligned_dates = chart_indexes[0]
                                for chart_index in chart_indexes[1:]:
                                    aligned_dates = aligned_dates.intersection(chart_index)
                                if any(len(index) != len(aligned_dates) for index in chart_indexes):
                                    st.warning(f"Chart OHLCV dates differ for {selected}; using {len(aligned_dates)} common sessions (50 required). Missing dates are excluded, not fabricated.")
                                if 50 <= len(aligned_dates) < 200:
                                    st.warning(f"Only {len(aligned_dates)} aligned OHLCV sessions for {selected}; chart displays 50-SMA without 200-SMA.")
                                image_bytes = cached_symbol_chart(
                                    snapshot_identity(), selected, open_frame, high, low, close, volume,
                                    pivot=pivot, stop=stop)
                                st.image(image_bytes, caption=f"{selected} · research only · unverified corporate actions")
                            except (ValueError, KeyError) as exc:
                                st.warning("Chart unavailable: " + str(exc))

                with st.expander("Candidate historical breakout evidence", expanded=False):
                    st.caption("Read-only technical outcomes for current setup candidates. "
                               "This is not a forecast, a VCP backtest, or an executable return study.")
                    if st.button("Check candidate breakout history", key="edge_candidate_replay"):
                        symbols = candidates["Symbol"].dropna().astype(str).unique().tolist() if "Symbol" in candidates else []
                        symbols = [s for s in symbols if s in close.columns]
                        if not symbols:
                            st.info("No current candidates with aligned historical OHLCV.")
                        else:
                            with st.spinner("Checking historical technical outcomes..."):
                                from edge_core.historical_replay import replay_breakout_rules
                                research = replay_breakout_rules(
                                    close[symbols], high[symbols], low[symbols], volume[symbols],
                                    start=close.index[max(0, len(close)-252)])
                            st.session_state["edge_candidate_history"] = research
                            st.session_state["edge_candidate_symbols"] = symbols
                    candidate_history = st.session_state.get("edge_candidate_history")
                    if candidate_history is not None:
                        st.caption("Last evaluated candidate symbols: " +
                                   str(len(st.session_state.get("edge_candidate_symbols", []))) +
                                   ". Re-run after refreshing the snapshot or candidate list.")
                        if not candidate_history.empty:
                            counts = candidate_history.groupby(["Symbol", "Outcome"]).size().unstack(fill_value=0)
                            st.dataframe(numbered(counts.reset_index()), use_container_width=True)
                        else:
                            st.info("No qualifying historical breakout events for this candidate cohort.")
                        export_section("Candidate breakout history", candidate_history,
                                       "edge_candidate_breakout_history")

                membership_file = SNAPSHOT_DIR / "current_membership.csv"
                provenance_file = SNAPSHOT_DIR / "evidence.json"
                leadership_frame = snapshot_table("leadership")
                if not is_provisional and membership_file.is_file() and provenance_file.is_file() and leadership_frame is not None:
                    provenance = json.loads(provenance_file.read_text())
                    if provenance.get("membership_sha256") == hashlib.sha256(membership_file.read_bytes()).hexdigest() and provenance.get("membership_source"):
                        members = pd.read_csv(membership_file, dtype={"ISIN Code": str})
                        period = st.date_input("Financial evidence period end", key="trade_readiness_period")
                        render_trader_readiness(leadership_frame, members, candidates, period.isoformat(), snapshot_fresh=snapshot_usable)
                    else:
                        st.warning("Trading readiness requires verified membership provenance.")

            except (ValueError, KeyError) as exc:
                st.error(str(exc))
elif page == "Portfolio & Journal":
    st.subheader("Portfolio & Journal")
    render_private_portfolio(prices,snapshot_usable, data_source='provisional' if is_provisional else 'verified')
elif page == "Financial Evidence Review":
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
                scored = cached_v1(snapshot_identity(), ranks.copy())
                financial_path = SNAPSHOT_DIR / "financial_records.csv"
                financial_records = pd.read_csv(financial_path).to_dict("records") if financial_path.is_file() else []
                st.warning("Select the reporting period end from the original company filings. No date is inferred.")
                period_end = st.date_input("Financial reporting period end", key="edge_financial_period_end")
                if st.checkbox("Open owner-only evidence intake", value=False):
                    from edge_financial_review import render_financial_evidence_review
                    render_financial_evidence_review(scored, membership, financial_records, period_end.isoformat())
        except (ValueError, KeyError, OSError, pd.errors.ParserError) as exc:
            st.error("Financial evidence review unavailable: " + str(exc))
st.caption("SPERA EDGE is not investment advice. No automatic execution, certified signals or return guarantees.")
