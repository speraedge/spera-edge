"""Single-command, fail-closed financial filing evidence audit bundle.

Runs source identity, comparability, document integrity, statement/document
matching, source transcription and growth reconciliation as one major milestone.
Does not certify issuer authenticity or financial figures.
"""
import argparse
import csv
import hashlib
import json
from pathlib import Path

from edge_core.financial_evidence import review_financials
from edge_core.financial_comparability import review_comparability
from edge_core.filing_document_provenance import audit_filing_documents
from edge_core.statement_document_reconciliation import reconcile_statement_documents
from edge_core.filing_value_reconciliation import reconcile_filing_values
from edge_core.financial_growth_reconciliation import reconcile_financial_growth


def _membership(path):
    with Path(path).open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if not reader.fieldnames or not {"Symbol", "ISIN Code"}.issubset(reader.fieldnames):
            raise ValueError("Official membership requires Symbol and ISIN Code")
        records = list(reader)
    if not records:
        raise ValueError("Empty official membership")
    result = {}
    seen_isins = set()
    for row in records:
        symbol = str(row["Symbol"] or "").strip().upper()
        isin = str(row["ISIN Code"] or "").strip().upper()
        if not symbol or not isin or symbol in result or isin in seen_isins:
            raise ValueError("Missing or duplicate official membership identity")
        result[symbol] = isin
        seen_isins.add(isin)
    return result


def run_bundle(membership, financials, document_register, documents_dir,
               transcriptions, output_dir):
    inputs = (membership, financials, document_register, transcriptions)
    for path in inputs:
        if not Path(path).is_file():
            raise FileNotFoundError(str(path))
    if not Path(documents_dir).is_dir():
        raise FileNotFoundError(str(documents_dir))
    identities = _membership(membership)
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    source = review_financials(financials, out / "financial", identities)
    comparable = review_comparability(financials, out / "comparability")
    documents = audit_filing_documents(document_register, documents_dir, out / "documents")
    doc_review = out / "documents" / "filing_document_review.csv"
    statement = reconcile_statement_documents(financials, doc_review, out / "statement")
    values = reconcile_filing_values(financials, transcriptions, out / "values", doc_review)
    growth = reconcile_financial_growth(
        out / "financial" / "financial_evidence_review.csv",
        out / "comparability" / "financial_comparability.csv",
        out / "growth")
    summary = {
        "input_sha256": {Path(p).name: hashlib.sha256(Path(p).read_bytes()).hexdigest()
                         for p in inputs},
        "membership_count": len(identities),
        "financial_source": source,
        "comparability": comparable,
        "document_provenance": documents,
        "statement_document": statement,
        "filing_values": values,
        "growth_reconciliation": growth,
        "certified": False,
        "ready_for_trading_signals": False,
        "manual_or_independent_review_required": True,
    }
    (out / "evidence_bundle_summary.json").write_text(
        json.dumps(summary, indent=2), encoding="utf-8")
    return summary


def main():
    parser = argparse.ArgumentParser()
    for name in ("membership", "financials", "document-register", "documents-dir",
                 "transcriptions", "output"):
        parser.add_argument("--" + name, required=True)
    args = parser.parse_args()
    summary = run_bundle(args.membership, args.financials, args.document_register,
                         args.documents_dir, args.transcriptions, args.output)
    print(json.dumps({"certified": False, "financial_rows": summary["financial_source"]["rows"],
                      "bundle": str(Path(args.output) / "evidence_bundle_summary.json")}, indent=2))


if __name__ == "__main__":
    main()
