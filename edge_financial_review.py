"""Authenticated operator review. Never upgrades financial records to certified."""
import uuid
import json

from edge_core.financial_evidence_ledger import FinancialEvidenceLedger
from edge_core.manual_evidence_queue import build_queue
from edge_core.evidence_shortlist import evidence_shortlist
from edge_core.acquisition_review_import import validate_acquisition_import, import_acquisition_review


def render_financial_evidence_review(scored, membership, financial_records, expected_period_end):
    import streamlit as st
    from edge_core.d1_store import d1_query
    from edge_workspace import identity_owner

    st.subheader("Financial evidence review (research only)")
    try:
        allowed = st.secrets.get("EDGE_JOURNAL_ALLOWED_EMAILS", [])
        configured = "auth" in st.secrets
    except FileNotFoundError:
        allowed, configured = [], False
    if isinstance(allowed, str):
        allowed = [x.strip() for x in allowed.split(",")]
    if not allowed or not configured:
        st.info("Evidence intake locked until owner OIDC access is configured.")
        return
    if not st.user.is_logged_in:
        if st.button("Sign in for financial evidence review"):
            st.login()
        return
    try:
        owner = identity_owner(dict(st.user), allowed)
    except ValueError:
        st.error("This account is not authorized to review financial evidence.")
        return
    keys = ("EDGE_CF_ACCOUNT_ID", "EDGE_D1_DATABASE_ID", "EDGE_CF_API_TOKEN")
    credentials = [st.secrets.get(k) for k in keys]
    if not all(credentials):
        st.error("Private EDGE D1 credentials not configured.")
        return

    def query(sql, params=()):
        return d1_query(sql, params, account_id=credentials[0],
                        database_id=credentials[1], token=credentials[2])

    try:
        candidates = evidence_shortlist(scored, membership)
        queue = build_queue(candidates, financial_records,
                            expected_period_end=expected_period_end)
        st.caption("Only shortlisted companies are shown. Submissions remain quarantined and unverified.")
        if not queue:
            st.info("No evidence review requests for this snapshot.")
            return
        st.dataframe(queue, use_container_width=True)
        ledger = FinancialEvidenceLedger(owner, query)
        ledger.initialize()
        choices = {str(i) + ": " + x["symbol"] + " / " + x["isin"]: x for i, x in enumerate(queue)}
        selected = st.selectbox("Evidence request", list(choices))
        item = choices[selected]
        if "edge_financial_event_id" not in st.session_state:
            st.session_state["edge_financial_event_id"] = str(uuid.uuid4())
        with st.form("edge_financial_evidence_intake"):
            revenue = st.text_input("Revenue (as reported, consistent units)")
            pat = st.text_input("PAT (same reporting basis and units)")
            published_on = st.date_input("Publication date")
            source_url = st.text_input("Original source document HTTPS URL")
            submit = st.form_submit_button("Submit for independent verification")
        if submit:
            submission = {k: item[k] for k in ("symbol", "isin", "period_end", "period_type", "basis")}
            submission.update(revenue=revenue, pat=pat,
                              published_on=published_on.isoformat(), source_url=source_url)
            ledger.append_intake([item], submission,
                                 event_id=st.session_state["edge_financial_event_id"])
            st.session_state["edge_financial_event_id"] = str(uuid.uuid4())
            st.success("Evidence saved as QUARANTINED_UNVERIFIED; not certified.")
        st.divider()
        st.caption("Official acquisition outcomes (uncertified)")
        uploaded = st.file_uploader("Import acquisition review JSON", type=["json"],
                                    key="edge_acquisition_review")
        if uploaded is not None:
            try:
                if uploaded.size > 1024 * 1024:
                    raise ValueError("Acquisition review exceeds 1 MB upload limit")
                imported = json.loads(uploaded.getvalue().decode("utf-8"))
                eligible = validate_acquisition_import(imported, queue)
                st.caption(f"{len(eligible)} validated unverified outcomes")
                st.dataframe(eligible, use_container_width=True)
                if st.button("Append validated unverified review events"):
                    events = import_acquisition_review(ledger, queue, imported)
                    st.success(f"{len(events)} review events recorded or safely replayed; not certified.")
            except (ValueError, KeyError, TypeError, UnicodeError) as exc:
                st.error("Import rejected: " + str(exc))
        history = ledger.events()
        if history:
            st.caption("Private append-only evidence history (owner-scoped)")
            st.dataframe(history, use_container_width=True)
        else:
            st.info("No financial evidence submissions recorded yet.")
    except (ValueError, KeyError, TypeError) as exc:
        st.error("Evidence review blocked: " + str(exc))
    except Exception:
        st.error("Private evidence service unavailable. No certification or trading decision permitted.")
