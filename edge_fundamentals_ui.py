"""Trade Desk fundamentals: public baseline + private owner-scoped D1 overlay."""
from pathlib import Path
import pandas as pd
import streamlit as st
from edge_core.d1_store import d1_query
from edge_core.manual_fundamentals import ManualFundamentals, FIELDS, merge_in_memory
from edge_workspace import identity_owner
from edge_core.fundamentals_privacy import validate_public_csv


def render_fundamentals(root=Path("data/latest")):
    st.subheader("Fundamentals (research only)")
    path = Path(root) / "fundamentals_auto.csv"
    if not path.exists():
        st.info("Automatic fundamentals have not been published yet.")
        return
    try:
        validate_public_csv(path)
        auto = pd.read_csv(path, keep_default_na=False)
    except (ValueError, OSError) as exc:
        st.error("Public fundamentals snapshot failed validation.")
        return
    symbols = auto["Symbol"].tolist()
    if not symbols:
        st.info("No fundamentals available.")
        return
    symbol = st.selectbox("Company", symbols, key="edge_fundamentals_symbol")
    baseline = auto.loc[auto["Symbol"] == symbol].iloc[0].to_dict()
    st.caption("Public automatic baseline; missing exchange values are not estimated.")
    st.dataframe(pd.DataFrame([baseline]), hide_index=True, use_container_width=True)
    try:
        allowed = st.secrets.get("EDGE_JOURNAL_ALLOWED_EMAILS", [])
        configured = "auth" in st.secrets
    except FileNotFoundError:
        allowed, configured = [], False
    if isinstance(allowed, str):
        allowed = [x.strip() for x in allowed.split(",")]
    if not configured or not allowed:
        st.info("Private manual entry is locked until OIDC and owner allowlist are configured.")
        return
    if not st.user.is_logged_in:
        if st.button("Sign in for private fundamentals"):
            st.login()
        return
    try:
        owner = identity_owner(dict(st.user), allowed)
    except ValueError:
        st.error("Verified owner authorization required.")
        return
    keys = ("EDGE_CF_ACCOUNT_ID", "EDGE_D1_DATABASE_ID", "EDGE_CF_API_TOKEN")
    credentials = [st.secrets.get(key) for key in keys]
    if not all(credentials):
        st.error("Private D1 credentials unavailable.")
        return
    def query(sql, params=()):
        return d1_query(sql, params, account_id=credentials[0],
                        database_id=credentials[1], token=credentials[2])
    try:
        store = ManualFundamentals(owner, query)
        store.initialize()
        manual = store.get(symbol)
    except Exception:
        st.error("Private fundamentals unavailable. No manual data was loaded.")
        return
    st.caption("Your manual values are stored only in private D1. They are not exported, logged or cached.")
    merged = merge_in_memory(baseline, manual)
    st.dataframe(pd.DataFrame([merged]), hide_index=True, use_container_width=True)
    with st.form("edge_private_fundamentals_form"):
        entries = {}
        labels = {"pe": "P/E", "market_cap": "Market cap", "quarter_revenue": "Quarter revenue",
                  "quarter_pat": "Quarter PAT", "quarter_eps": "Quarter EPS"}
        for field in FIELDS:
            prior = manual.get(field) if manual else None
            entries[field] = st.number_input(labels[field], value=float(prior or 0),
                                              min_value=0.0 if field != "quarter_pat" else None,
                                              key="edge_manual_" + field)
        entries["quarter_end"] = st.text_input("Quarter end (YYYY-MM-DD)",
                                               value=(manual or {}).get("quarter_end") or "")
        submitted = st.form_submit_button("Save privately to D1")
    if submitted:
        try:
            import datetime
            if entries["quarter_end"]:
                datetime.date.fromisoformat(entries["quarter_end"])
            store.save(symbol, entries)
            st.success("Saved to your private D1 record. Public CSV unchanged.")
            st.rerun()
        except (ValueError, TypeError):
            st.error("Invalid manual values or quarter date.")
        except Exception:
            st.error("Private D1 write failed; no public fallback.")
