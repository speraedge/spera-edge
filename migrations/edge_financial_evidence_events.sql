-- SPERA EDGE Milestone 2 evidence ledger. Apply to EDGE D1 only after review.
-- Append-only history; no financial PASS promotion or destructive migrations.
CREATE TABLE IF NOT EXISTS edge_financial_evidence_events (
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
  previous_event_id TEXT,
  FOREIGN KEY(previous_event_id) REFERENCES edge_financial_evidence_events(event_id)
);
CREATE INDEX IF NOT EXISTS edge_financial_evidence_owner_lookup
  ON edge_financial_evidence_events(owner_id, isin, period_end, period_type, basis, created_utc);
CREATE TRIGGER IF NOT EXISTS edge_financial_evidence_no_update
BEFORE UPDATE ON edge_financial_evidence_events
BEGIN SELECT RAISE(ABORT, 'Financial evidence is append-only'); END;
CREATE TRIGGER IF NOT EXISTS edge_financial_evidence_no_delete
BEFORE DELETE ON edge_financial_evidence_events
BEGIN SELECT RAISE(ABORT, 'Financial evidence is append-only'); END;
