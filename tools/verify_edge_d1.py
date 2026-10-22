"""Safe, opt-in live EDGE D1 smoke check. Never writes trading or certified records.

Usage: python tools/verify_edge_d1.py --live
Requires EDGE_CF_ACCOUNT_ID, EDGE_D1_DATABASE_ID, EDGE_CF_API_TOKEN in environment.
"""
import argparse
import json
import os
import uuid
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from edge_core.d1_store import d1_query
from edge_core.financial_evidence_ledger import FinancialEvidenceLedger
from edge_core.acquisition_review_import import import_acquisition_review


def verify(query, *, live=False):
    if not live:
        raise ValueError("Live D1 verification requires explicit --live")
    owner = "edge-smoke-" + uuid.uuid4().hex
    other = "edge-smoke-" + uuid.uuid4().hex
    ledger = FinancialEvidenceLedger(owner, query)
    ledger.initialize()
    queue = [{"symbol": "EDGE_TEST", "isin": "INE000A01001",
              "period_end": "2026-09-30", "period_type": "Q",
              "basis": "CONSOLIDATED"}]
    submission = dict(queue[0], revenue="1", pat="0",
                      published_on="2026-10-20",
                      source_url="https://example.com/smoke-test.pdf")
    event_id = "edge-smoke-" + uuid.uuid4().hex
    ledger.append_intake(queue, submission, event_id=event_id)
    ledger.append_intake(queue, submission, event_id=event_id)
    own = [r for r in ledger.events() if r["event_id"] == event_id]
    foreign = [r for r in FinancialEvidenceLedger(other, query).events()
               if r["event_id"] == event_id]
    if len(own) != 1 or foreign or own[0]["intake_status"] != "QUARANTINED_UNVERIFIED":
        raise RuntimeError("Live owner isolation or idempotency verification failed")
    reconciliation = dict(queue[0], acquisition_status="HTTP_403", certified=False)
    payload = {"review": [reconciliation], "certified": False,
               "ready_for_trading_signals": False}
    imported = import_acquisition_review(ledger, queue, payload)
    replayed = import_acquisition_review(ledger, queue, payload)
    if imported != replayed:
        raise RuntimeError("Reconciliation replay mismatch")
    records = [r for r in ledger.events() if r["event_id"] == imported[0]]
    foreign_records = [r for r in FinancialEvidenceLedger(other, query).events()
                       if r["event_id"] == imported[0]]
    if len(records) != 1 or foreign_records or records[0]["intake_status"] != "REVIEW_REQUIRED":
        raise RuntimeError("Reconciliation owner isolation or quarantine failed")
    if json.loads(records[0]["payload_json"]).get("certified") is not False:
        raise RuntimeError("Reconciliation certification invariant failed")
    for statement in (
        "UPDATE edge_financial_evidence_events SET intake_status='REJECTED' WHERE event_id=?",
        "DELETE FROM edge_financial_evidence_events WHERE event_id=?",
    ):
        try:
            query(statement, (imported[0],))
        except Exception:
            pass
        else:
            raise RuntimeError("Append-only D1 protection missing")
    if len([row for row in ledger.events() if row["event_id"] == imported[0]]) != 1:
        raise RuntimeError("Synthetic reconciliation event was modified")
    return {"status": "PASS", "live": True, "quarantined": True,
            "reconciliation_review_required": True, "reconciliation_idempotency": True,
            "owner_isolation": True, "idempotency": True,
            "certified": False, "synthetic_event_id": event_id}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--live", action="store_true")
    args = parser.parse_args()
    if not args.live:
        parser.error("Explicit --live required to write synthetic evidence")
    for name in ("EDGE_CF_ACCOUNT_ID", "EDGE_D1_DATABASE_ID", "EDGE_CF_API_TOKEN"):
        if not os.environ.get(name):
            parser.error("Missing " + name)
    print(json.dumps(verify(d1_query, live=True), indent=2))


if __name__ == "__main__":
    main()
