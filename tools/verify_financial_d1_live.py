"""Opt-in EDGE D1 live financial intake smoke test; never certifies a filing.

Run only against an explicitly chosen EDGE D1 database with credentials in
environment. Creates one quarantined synthetic test event and verifies readback.
"""
import argparse
import os
import uuid
from datetime import date, timedelta

from edge_core.d1_store import d1_query
from edge_core.financial_evidence_ledger import FinancialEvidenceLedger


def verify_live():
    keys = ("EDGE_CF_ACCOUNT_ID", "EDGE_D1_DATABASE_ID", "EDGE_CF_API_TOKEN")
    if not all(os.environ.get(key) for key in keys):
        raise RuntimeError("EDGE D1 environment credentials required")
    owner = "edge-smoke-" + uuid.uuid4().hex
    event_id = "edge-smoke-" + uuid.uuid4().hex
    ledger = FinancialEvidenceLedger(owner, d1_query)
    ledger.initialize()
    period = (date.today() - timedelta(days=40)).isoformat()
    published = (date.today() - timedelta(days=10)).isoformat()
    queue = [{"symbol": "EDGESMOKE", "isin": "INE000A01001",
              "period_end": period, "period_type": "Q", "basis": "CONSOLIDATED"}]
    submission = dict(queue[0], revenue="100", pat="10",
                      published_on=published,
                      source_url="https://example.com/synthetic-test-only")
    ledger.append_intake(queue, submission, event_id=event_id)
    events = ledger.events()
    if len(events) != 1 or events[0]["event_id"] != event_id or events[0]["intake_status"] != "QUARANTINED_UNVERIFIED":
        raise RuntimeError("EDGE D1 evidence write/readback mismatch")
    other = FinancialEvidenceLedger("edge-other-owner-" + uuid.uuid4().hex, d1_query)
    if other.events():
        raise RuntimeError("EDGE D1 owner isolation failed")
    ledger.append_intake(queue, submission, event_id=event_id)
    if len(ledger.events()) != 1:
        raise RuntimeError("EDGE D1 idempotency failed")
    print("PASS: synthetic quarantined intake, owner isolation and idempotent readback")
    print("Synthetic event retained in append-only D1 ledger; no certification performed.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--confirm-live-write", action="store_true",
                        help="Explicitly authorize one synthetic append-only write to EDGE D1")
    args = parser.parse_args()
    if not args.confirm_live_write:
        parser.error("Live D1 write requires --confirm-live-write")
    verify_live()
