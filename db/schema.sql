-- SPERA EDGE independent D1 schema. Execute in the NEW spera-edge-db only.
CREATE TABLE IF NOT EXISTS edge_snapshot_runs (
  run_id TEXT PRIMARY KEY,
  universe_id TEXT NOT NULL,
  weekly_key TEXT NOT NULL,
  source TEXT NOT NULL,
  quality TEXT NOT NULL CHECK (quality IN ('PASS','REVIEW','FAIL')),
  is_certified INTEGER NOT NULL DEFAULT 0 CHECK (is_certified IN (0,1)),
  rows_count INTEGER NOT NULL DEFAULT 0,
  generated_utc TEXT NOT NULL,
  source_hash TEXT NOT NULL,
  metadata_json TEXT NOT NULL,
  UNIQUE(universe_id, weekly_key, source_hash)
);
CREATE INDEX IF NOT EXISTS idx_edge_snapshot_runs_week
  ON edge_snapshot_runs(universe_id, weekly_key DESC);
CREATE TABLE IF NOT EXISTS edge_leadership (
  run_id TEXT NOT NULL REFERENCES edge_snapshot_runs(run_id),
  symbol TEXT NOT NULL,
  data_quality TEXT NOT NULL CHECK(data_quality IN ('PASS','REVIEW','FAIL')),
  momentum_rank INTEGER,
  source_row_json TEXT NOT NULL,
  PRIMARY KEY(run_id, symbol)
);
CREATE INDEX IF NOT EXISTS idx_edge_leadership_rank ON edge_leadership(run_id,momentum_rank);
CREATE TABLE IF NOT EXISTS edge_sector_summary (
  run_id TEXT NOT NULL REFERENCES edge_snapshot_runs(run_id),
  sector TEXT NOT NULL,
  sector_rank INTEGER,
  source_row_json TEXT NOT NULL,
  PRIMARY KEY(run_id,sector)
);
CREATE TABLE IF NOT EXISTS edge_journal (
  journal_id TEXT PRIMARY KEY,
  created_utc TEXT NOT NULL,
  symbol TEXT NOT NULL,
  side TEXT NOT NULL CHECK(side IN ('LONG','SHORT')),
  quantity INTEGER NOT NULL CHECK(quantity>0),
  entry_price REAL NOT NULL CHECK(entry_price>0),
  stop_price REAL NOT NULL CHECK(stop_price>0),
  note TEXT NOT NULL DEFAULT '',
  source TEXT NOT NULL DEFAULT 'EDGE'
);
