"""Initialize only the separate EDGE D1 database; statements are idempotent."""
from pathlib import Path
from edge_core.d1_store import d1_query

def initialize(path="db/schema.sql"):
    sql=Path(path).read_text()
    statements=[s.strip() for s in sql.split(";") if s.strip()]
    for statement in statements:
        d1_query(statement)
    return len(statements)

if __name__=="__main__":
    print(f"Initialized {initialize()} schema statements in EDGE D1")
