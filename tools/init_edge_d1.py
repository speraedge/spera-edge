"""Safe one-time EDGE D1 schema initializer; no original SPERA database access."""
from pathlib import Path
from edge_core.d1_store import d1_query

def initialize(path="db/schema.sql"):
    sql=Path(path).read_text()
    statements=[s.strip() for s in sql.split(";") if s.strip() and not s.strip().startswith("-- SPERA SOURCE")]
    for statement in statements:
        d1_query(statement)
    return len(statements)

if __name__=="__main__":
    print(f"Initialized {initialize()} schema statements in EDGE D1")
