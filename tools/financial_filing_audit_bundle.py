"""One-command fail-closed financial filing audit bundle.

Requires explicit official filing URLs and independent transcriptions. No
automatic source discovery, certification, or trading-signal publication.
"""
import argparse
import csv
import json
from collections import Counter
from pathlib import Path

from tools.acquire_official_filings import acquire
from edge_core.filing_document_provenance import audit_filing_documents
from edge_core.statement_document_reconciliation import reconcile_statement_documents
from edge_core.filing_value_reconciliation import reconcile_filing_values
from edge_core.financial_comparability import review_comparability


def run_bundle(source_register, financials, transcriptions, output, *, session=None):
    out = Path(output)
    out.mkdir(parents=True, exist_ok=True)
    acquired = acquire(source_register, out / "documents", session=session)
    rows = []
    with Path(source_register).open(encoding="utf-8-sig", newline="") as stream:
        for record in csv.DictReader(stream):
            rows.append(record)
    if len(rows) != len(acquired["documents"]):
        raise ValueError("Acquisition manifest row count mismatch")
    provenance = out / "document_register.csv"
    fields = ["symbol", "isin", "period_end", "period_type", "basis", "published_on", "source_url",
              "document_filename", "expected_sha256"]
    with provenance.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        for source, result in zip(rows, acquired["documents"]):
            writer.writerow({
                "symbol": source["symbol"], "isin": source["isin"],
                "period_end": source["period_end"],
                "period_type": source.get("period_type", ""),
                "basis": source.get("basis", ""),
                "published_on": source.get("published_on", ""),
                "source_url": source["source_url"],
                "document_filename": result["file"],
                "expected_sha256": result["sha256"],
            })
    audit = audit_filing_documents(provenance, out / "documents", out / "review")
    docs = out / "review" / "filing_document_review.csv"
    statements = reconcile_statement_documents(financials, docs, out / "review")
    values = reconcile_filing_values(financials, transcriptions, out / "review",
                                     document_review_csv=docs)
    comparable = review_comparability(financials, out / "review")
    statuses = Counter(item["status"] for item in acquired["documents"])
    summary = {
        "acquisition": dict(statuses),
        "document_review": audit["status_counts"],
        "statement_match": statements["status_counts"],
        "value_reconciliation": values["status_counts"],
        "comparability": comparable["status_counts"],
        "certified": False,
        "ready_for_trading_signals": False,
        "limitations": [
            "Only operator-supplied official URLs are fetched; no automatic discovery.",
            "Downloaded bytes and transcription matches do not prove issuer authenticity.",
            "Publication dates, restatements and values require independent verification.",
        ],
    }
    (out / "bundle_summary.json").write_text(json.dumps(summary, indent=2))
    return summary


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--register", required=True)
    parser.add_argument("--financials", required=True)
    parser.add_argument("--transcriptions", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    print(json.dumps(run_bundle(args.register, args.financials,
                                args.transcriptions, args.output), indent=2))


if __name__ == "__main__":
    main()
