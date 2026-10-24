"""Run the existing public fundamentals fetcher from a local Windows/Mac checkout.

Usage (from any working directory):
    python tools/fetch_fundamentals_local.py
Requires installed requirements.txt and official data/latest/current_membership.csv.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from edge_fundamentals import run
from edge_core.fundamentals_privacy import validate_public_csv

MEMBERSHIP = ROOT / "data" / "latest" / "current_membership.csv"
OUTPUT = ROOT / "data" / "latest" / "fundamentals_auto.csv"
MAPPING = ROOT / "data" / "latest" / "bse_mapping.csv"


def main():
    if not MEMBERSHIP.is_file():
        raise SystemExit("Missing official membership CSV: " + str(MEMBERSHIP))
    # Reuse the exact existing exchange-fetch and privacy-gated publication logic.
    # The underlying fetcher writes atomically after constructing all rows.
    rows = run(membership=str(MEMBERSHIP), output=str(OUTPUT), mapping_path=str(MAPPING))
    validate_public_csv(OUTPUT)
    successes = sum(row["Status"] == "AUTO" for row in rows)
    if not successes:
        # The fetcher may have published all-failed rows. Do not claim a
        # successful fundamentals acquisition or recommend uploading them.
        raise SystemExit("No verified fundamentals acquired (0 AUTO rows). Do NOT upload this CSV; exchange data may be unavailable.")
    print(f"SUCCESS: Saved {OUTPUT} ({len(rows)} symbols; {successes} verified AUTO rows).")
    print("Review the CSV and upload ONLY data/latest/fundamentals_auto.csv to GitHub.")


if __name__ == "__main__":
    main()
