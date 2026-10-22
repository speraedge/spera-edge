"""Import a downloaded NSE corporate-actions CSV without granting certification.

The operator must download the CSV from the official NSE corporate-filings
page. This importer never scrapes endpoints or fabricates ISINs or factors.
"""
import argparse
import csv
import hashlib
import json
from pathlib import Path

from edge_core.corporate_action_evidence import review_events

NSE_ACTIONS_PAGE = "https://www.nseindia.com/companies-listing/corporate-filings-actions"
REQUIRED = {"SYMBOL", "PURPOSE", "EX-DATE"}


def import_nse_actions(source_csv, membership_csv, output_dir):
    source = Path(source_csv)
    membership = Path(membership_csv)
    with membership.open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        if not reader.fieldnames or not {"Symbol", "ISIN Code"}.issubset(reader.fieldnames):
            raise ValueError("Membership requires Symbol and ISIN Code")
        members = list(reader)
    identities = {}
    for item in members:
        symbol = (item["Symbol"] or "").strip().upper()
        isin = (item["ISIN Code"] or "").strip().upper()
        if not symbol or not isin or symbol in identities or isin in identities.values():
            raise ValueError("Missing or duplicate official membership identity")
        identities[symbol] = isin
    with source.open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        if not reader.fieldnames:
            raise ValueError("Corporate-actions CSV is missing its header")
        cols = {x.strip().upper(): x for x in reader.fieldnames}
        if not REQUIRED.issubset(cols):
            raise ValueError("NSE export missing SYMBOL, PURPOSE or EX-DATE")
        records = list(reader)
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    normalized = out / "nse_actions_normalized.csv"
    fields = ["symbol", "isin", "purpose", "ex_date", "source_url"]
    with normalized.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        for row in records:
            symbol = (row[cols["SYMBOL"]] or "").strip().upper()
            writer.writerow({"symbol": symbol, "isin": identities.get(symbol, ""),
                             "purpose": row[cols["PURPOSE"]] or "",
                             "ex_date": row[cols["EX-DATE"]] or "",
                             "source_url": ""})
    review = review_events(normalized, out / "review", identities)
    manifest = {"source_type": "OPERATOR_DOWNLOADED_NSE_CSV",
                "source_page": NSE_ACTIONS_PAGE,
                "original_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
                "membership_sha256": hashlib.sha256(membership.read_bytes()).hexdigest(),
                "source_rows": len(records), "normalized_rows": len(records),
                "official_download_verified": False,
                "individual_event_sources_verified": False,
                "historical_coverage_verified": False,
                "adjustment_factors_approved": False,
                "certified": False, "review": review}
    (out / "import_manifest.json").write_text(json.dumps(manifest, indent=2))
    return manifest


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--nse-export", required=True)
    parser.add_argument("--membership", required=True)
    parser.add_argument("--output", default="data/evidence_review/nse_import")
    args = parser.parse_args()
    print(json.dumps(import_nse_actions(args.nse_export, args.membership, args.output), indent=2))


if __name__ == "__main__":
    main()
