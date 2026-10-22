"""Safe operator-facing summary for the opt-in D1 verification command.

Run from the repository root with explicit EDGE credentials:
  python tools/verify_edge_d1.py --live

This performs only synthetic evidence writes; it never certifies companies.
Do not copy tokens or database credentials into logs, issues or chat.
"""
from pathlib import Path


def check_live_readiness(environ, script=None):
    required = ("EDGE_CF_ACCOUNT_ID", "EDGE_D1_DATABASE_ID", "EDGE_CF_API_TOKEN")
    missing = [key for key in required if not environ.get(key)]
    path = Path(script or "tools/verify_edge_d1.py")
    return {
        "ready": not missing and path.is_file(),
        "missing_credentials": missing,
        "verifier_present": path.is_file(),
        "command": "python tools/verify_edge_d1.py --live",
        "production_data_certified": False,
    }


if __name__ == "__main__":
    import json
    import os
    print(json.dumps(check_live_readiness(os.environ), indent=2))
