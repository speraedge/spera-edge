"""Private, owner-scoped D1 fundamentals. No public export and no shared cache."""
import math
import re

CREATE_SQL = """CREATE TABLE IF NOT EXISTS edge_manual_fundamentals (
 owner_id TEXT NOT NULL, symbol TEXT NOT NULL,
 pe REAL, market_cap REAL, quarter_revenue REAL, quarter_pat REAL,
 quarter_eps REAL, quarter_end TEXT, updated_utc TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
 PRIMARY KEY(owner_id, symbol))"""
FIELDS = ("pe", "market_cap", "quarter_revenue", "quarter_pat", "quarter_eps")
SYMBOL = re.compile(r"^[A-Z0-9.\-&]+$")


class ManualFundamentals:
    def __init__(self, owner, query):
        if not isinstance(owner, str) or not re.fullmatch(r"[a-f0-9]{64}", owner):
            raise ValueError("Verified owner hash required")
        self.owner, self.query = owner, query

    def initialize(self):
        self.query(CREATE_SQL)

    def get(self, symbol):
        if not SYMBOL.fullmatch(symbol):
            raise ValueError("Invalid symbol")
        rows = self.query(
            "SELECT symbol,pe,market_cap,quarter_revenue,quarter_pat,quarter_eps,quarter_end "
            "FROM edge_manual_fundamentals WHERE owner_id=? AND symbol=?",
            (self.owner, symbol))
        return rows[0] if rows else None

    def save(self, symbol, values):
        if not SYMBOL.fullmatch(symbol) or set(values) != set((*FIELDS, "quarter_end")):
            raise ValueError("Invalid manual fundamentals fields")
        for field in FIELDS:
            value = values[field]
            if value is not None and (not math.isfinite(float(value)) or
                                      (field in ("pe", "market_cap", "quarter_revenue", "quarter_eps") and float(value) < 0)):
                raise ValueError("Invalid manual financial value")
        self.query(
            "INSERT INTO edge_manual_fundamentals "
            "(owner_id,symbol,pe,market_cap,quarter_revenue,quarter_pat,quarter_eps,quarter_end) "
            "VALUES(?,?,?,?,?,?,?,?) ON CONFLICT(owner_id,symbol) DO UPDATE SET "
            "pe=excluded.pe,market_cap=excluded.market_cap,quarter_revenue=excluded.quarter_revenue,"
            "quarter_pat=excluded.quarter_pat,quarter_eps=excluded.quarter_eps,"
            "quarter_end=excluded.quarter_end,updated_utc=CURRENT_TIMESTAMP",
            (self.owner, symbol, *(values[f] for f in FIELDS), values["quarter_end"]))


def merge_in_memory(auto, manual):
    """Never write the merged record to public CSV, logs, or shared cache."""
    result = dict(auto)
    if manual:
        for field, public in (("pe", "PE"), ("market_cap", "Market_Cap"),
                              ("quarter_revenue", "Quarter_Revenue"),
                              ("quarter_pat", "Quarter_PAT"), ("quarter_eps", "Quarter_EPS"),
                              ("quarter_end", "Quarter_End")):
            if manual.get(field) is not None and manual.get(field) != "":
                result[public] = manual[field]
    return result
