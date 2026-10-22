"""Immutable private record schema and isolated infrastructure-test routing."""
import re

PRIVATE_TABLES = ('edge_trade_events', 'edge_setup_decisions', 'edge_decision_trade_links')


def initialize_private_schema(query):
    query('''CREATE TABLE IF NOT EXISTS edge_trade_events (
        owner_id TEXT NOT NULL, event_id TEXT NOT NULL, revision INTEGER NOT NULL,
        created_utc TEXT NOT NULL, payload TEXT NOT NULL,
        PRIMARY KEY(owner_id,event_id), UNIQUE(owner_id,revision))''')
    query('''CREATE TABLE IF NOT EXISTS edge_setup_decisions (
        owner_id TEXT NOT NULL, decision_id TEXT NOT NULL,
        created_utc TEXT NOT NULL, payload TEXT NOT NULL,
        PRIMARY KEY(owner_id,decision_id))''')
    query('''CREATE TABLE IF NOT EXISTS edge_decision_trade_links (
        owner_id TEXT NOT NULL, decision_id TEXT NOT NULL, event_id TEXT NOT NULL,
        created_utc TEXT NOT NULL, PRIMARY KEY(owner_id,decision_id,event_id),
        UNIQUE(owner_id,event_id))''')
    for table in PRIVATE_TABLES:
        for action in ('UPDATE', 'DELETE'):
            query(f'''CREATE TRIGGER IF NOT EXISTS {table}_immutable_{action.lower()}
                BEFORE {action} ON {table} BEGIN
                SELECT RAISE(ABORT, 'Private records are append-only'); END''')
    query('''CREATE TRIGGER IF NOT EXISTS edge_decision_trade_links_validate
        BEFORE INSERT ON edge_decision_trade_links BEGIN
        SELECT CASE WHEN NOT EXISTS (
            SELECT 1 FROM edge_setup_decisions AS decision
            JOIN edge_trade_events AS trade ON trade.owner_id=decision.owner_id
            WHERE decision.owner_id=NEW.owner_id AND decision.decision_id=NEW.decision_id
            AND trade.event_id=NEW.event_id
            AND json_extract(decision.payload,'$.decision')='TAKE'
            AND json_extract(trade.payload,'$.kind')='BUY'
            AND json_extract(decision.payload,'$.symbol')=json_extract(trade.payload,'$.symbol')
        ) THEN RAISE(ABORT, 'Link requires same-owner TAKE and recorded BUY') END; END''')


def synthetic_private_query(query, namespace):
    if not re.fullmatch(r'edge_audit_[a-f0-9]{32}_', namespace):
        raise ValueError('Invalid synthetic database namespace')
    def isolated(sql, params=()):
        for table in reversed(PRIVATE_TABLES):
            sql = sql.replace(table, namespace + table)
        return query(sql, params)
    return isolated


def validate_revisions(rows):
    if [row['revision'] for row in rows] != list(range(1, len(rows) + 1)):
        raise ValueError('Private ledger revision sequence is not contiguous')
