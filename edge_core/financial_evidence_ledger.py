"""Owner-scoped, append-only financial evidence intake; never certifies a filing."""
import hashlib
import json
import uuid
from datetime import datetime, timezone

from edge_core.manual_evidence_intake import review_intake, COLUMNS


class FinancialEvidenceLedger:
    def __init__(self, owner, query):
        if not owner or not callable(query):
            raise ValueError("Authenticated owner and D1 query required")
        self.owner, self.query = owner, query

    def initialize(self):
        self.query("""CREATE TABLE IF NOT EXISTS edge_financial_evidence_events (
            event_id TEXT PRIMARY KEY NOT NULL,
            owner_id TEXT NOT NULL,
            symbol TEXT NOT NULL,
            isin TEXT NOT NULL,
            period_end TEXT NOT NULL,
            period_type TEXT NOT NULL CHECK(period_type IN ('Q','FY')),
            basis TEXT NOT NULL CHECK(basis IN ('CONSOLIDATED','STANDALONE')),
            created_utc TEXT NOT NULL,
            event_kind TEXT NOT NULL CHECK(event_kind IN ('INTAKE','REVIEW_NOTE','SOURCE_RECONCILIATION','CORRECTION')),
            intake_status TEXT NOT NULL CHECK(intake_status IN ('QUARANTINED_UNVERIFIED','REJECTED','REVIEW_REQUIRED')),
            source_sha256 TEXT,
            payload_json TEXT NOT NULL,
            previous_event_id TEXT
        )""")
        self.query("""CREATE INDEX IF NOT EXISTS edge_financial_evidence_owner_lookup
            ON edge_financial_evidence_events(owner_id, isin, period_end, period_type, basis, created_utc)""")
        self.query("""CREATE TRIGGER IF NOT EXISTS edge_financial_evidence_no_update
            BEFORE UPDATE ON edge_financial_evidence_events
            BEGIN SELECT RAISE(ABORT, 'Financial evidence is append-only'); END""")
        self.query("""CREATE TRIGGER IF NOT EXISTS edge_financial_evidence_no_delete
            BEFORE DELETE ON edge_financial_evidence_events
            BEGIN SELECT RAISE(ABORT, 'Financial evidence is append-only'); END""")

    def events(self):
        return self.query("""SELECT event_id, created_utc, symbol, isin, period_end,
            period_type, basis, intake_status, payload_json
            FROM edge_financial_evidence_events WHERE owner_id=?
            ORDER BY created_utc, event_id""", (self.owner,))

    def append_intake(self, queue, submission, *, event_id=None):
        reviewed = review_intake(queue, [submission])
        if len(reviewed) != 1:
            raise ValueError("Expected exactly one reviewed submission")
        record = reviewed[0]
        if record["intake_status"] != "QUARANTINED_UNVERIFIED":
            raise ValueError("Invalid intake: " + record["intake_reason"])
        event_id = event_id or str(uuid.uuid4())
        payload = json.dumps(record, sort_keys=True, allow_nan=False)
        digest = hashlib.sha256(payload.encode()).hexdigest()
        rows = self.query("""INSERT INTO edge_financial_evidence_events
            (event_id, owner_id, symbol, isin, period_end, period_type, basis,
             created_utc, event_kind, intake_status, source_sha256, payload_json)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
            ON CONFLICT(event_id) DO NOTHING RETURNING event_id""",
            (event_id, self.owner, record["symbol"], record["isin"],
             record["period_end"], record["period_type"], record["basis"],
             datetime.now(timezone.utc).isoformat(), "INTAKE",
             "QUARANTINED_UNVERIFIED", None, payload))
        if rows:
            return event_id
        existing = self.query("""SELECT owner_id, payload_json FROM edge_financial_evidence_events
            WHERE event_id=?""", (event_id,))
        if not existing or existing[0]["owner_id"] != self.owner or existing[0]["payload_json"] != payload:
            raise ValueError("Event ID collision or altered replay")
        return event_id

    def append_reconciliation(self, queue, outcome, *, event_id=None):
        """Append an unverified source-acquisition outcome for a queued identity.

        Never accepts owner identity, certification or event status from input.
        Replays require the exact same event payload and owner.
        """
        allowed = {(str(x["symbol"]).strip().upper(), str(x["isin"]).strip().upper(),
                    str(x["period_end"]), str(x["period_type"]), str(x["basis"]))
                   for x in queue}
        key = tuple(str(outcome.get(k, "")).strip().upper() for k in
                    ("symbol", "isin", "period_end", "period_type", "basis"))
        if key not in allowed:
            raise ValueError("Reconciliation outcome not in owner review queue")
        status = str(outcome.get("acquisition_status", "")).strip().upper()
        if status not in ("SOURCE_NOT_FOUND", "AMBIGUOUS_SOURCE", "INVALID_PUBLICATION_DATE",
                          "INVALID_SOURCE_METADATA", "ACQUISITION_PENDING_UNVERIFIED",
                          "ACQUIRED_UNVERIFIED", "HTTP_403", "HTTP_429",
                          "HTTP_ERROR", "DOWNLOAD_ERROR", "INVALID_PDF",
                          "TOO_LARGE", "REVIEW_REQUIRED"):
            raise ValueError("Unknown or unsafe acquisition status")
        safe = {k: str(outcome.get(k, "")).strip() for k in
                ("symbol", "isin", "period_end", "period_type", "basis",
                 "acquisition_status", "source_url", "published_on", "document_sha256")}
        safe.update(certified=False, ready_for_trading_signals=False)
        payload = json.dumps(safe, sort_keys=True, allow_nan=False)
        event_id = event_id or str(uuid.uuid4())
        rows = self.query("""INSERT INTO edge_financial_evidence_events
            (event_id, owner_id, symbol, isin, period_end, period_type, basis,
             created_utc, event_kind, intake_status, source_sha256, payload_json)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
            ON CONFLICT(event_id) DO NOTHING RETURNING event_id""",
            (event_id, self.owner, *key, datetime.now(timezone.utc).isoformat(),
             "SOURCE_RECONCILIATION", "REVIEW_REQUIRED",
             safe["document_sha256"] or None, payload))
        if rows:
            return event_id
        existing = self.query("""SELECT owner_id, payload_json FROM edge_financial_evidence_events
            WHERE event_id=?""", (event_id,))
        if not existing or existing[0]["owner_id"] != self.owner or existing[0]["payload_json"] != payload:
            raise ValueError("Event ID collision or altered reconciliation replay")
        return event_id
