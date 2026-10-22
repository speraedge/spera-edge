"""Orchestrate shortlisted filing acquisition and fail-closed financial review.

All inputs are explicit and auditable. This module neither discovers exchange
URLs nor certifies financial values or trading signals.
"""
import csv
import json
from collections import Counter
from pathlib import Path

from edge_core.official_acquisition_bridge import prepare_official_acquisition
from tools.financial_filing_audit_bundle import run_bundle


def run_shortlist_financial_audit(shortlist, filing_references, financial_records,
                                  expected_period_end, output, *,
                                  period_type="Q", basis="CONSOLIDATED",
                                  transcriptions=None, session=None):
    out = Path(output)
    out.mkdir(parents=True, exist_ok=True)
    bridge = prepare_official_acquisition(
        shortlist, filing_references, financial_records, expected_period_end,
        out / "intake", period_type=period_type, basis=basis)
    register = out / "intake" / "official_acquisition_register.csv"
    audit = None
    # Do not run a misleading value reconciliation without an explicit
    # transcription set. Empty/missing inputs stay in operator review.
    if bridge["registered"] and transcriptions is not None:
        financials = out / "financials.csv"
        transcribed = out / "transcriptions.csv"
        required = ("symbol", "isin", "period_end", "period_type", "basis",
                    "source_url", "published_on", "revenue", "pat")
        with financials.open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=required)
            writer.writeheader()
            writer.writerows([{k: row.get(k, "") for k in required} for row in financial_records])
        with transcribed.open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=(*required, "document_sha256"))
            writer.writeheader()
            writer.writerows([{k: row.get(k, "") for k in (*required, "document_sha256")}
                              for row in transcriptions])
        audit = run_bundle(register, financials, transcribed, out / "audit", session=session)
    with register.open(newline="", encoding="utf-8") as stream:
        registered = list(csv.DictReader(stream))
    publication_by_key = {
        (row["symbol"].strip().upper(), row["isin"].strip().upper(),
         row["period_end"], row["period_type"], row["basis"]): row["published_on"]
        for row in registered
    }
    outcomes = []
    acquired = {}
    if audit is not None:
        manifest = json.loads((out / "audit" / "documents" / "acquisition_manifest.json").read_text())
        for document in manifest["documents"]:
            key = (document["symbol"].strip().upper(), document["isin"].strip().upper(),
                   document["period_end"])
            raw_status = document["status"]
            status = raw_status if raw_status in (
                "ACQUIRED_UNVERIFIED", "HTTP_403", "HTTP_429", "HTTP_ERROR"
            ) else "REVIEW_REQUIRED"
            acquired[key] = {
                "acquisition_status": status,
                "source_url": document.get("source_url", ""),
                "document_sha256": document.get("sha256", ""),
            }
    for decision in bridge["review"]:
        key = (decision["symbol"], decision["isin"], decision["period_end"])
        evidence = acquired.get(key, {})
        full_key = (decision["symbol"], decision["isin"], decision["period_end"],
                    decision["period_type"], decision["basis"])
        published_on = publication_by_key.get(full_key, "")
        outcomes.append({**decision,
                         "acquisition_status": evidence.get(
                             "acquisition_status", decision["acquisition_status"]),
                         "source_url": evidence.get("source_url", ""),
                         "document_sha256": evidence.get("document_sha256", ""),
                         "published_on": published_on,
                         "status": "REVIEW_REQUIRED", "certified": False})
    # A downloaded PDF is not a reconciled financial statement. Surface a
    # per-candidate audit decision from all four independent evidence layers.
    reconciliation = {}
    if audit is not None:
        review_dir = out / "audit" / "review"
        layers = (
            ("filing_document_review.csv", "document_status", "status"),
            ("statement_document_reconciliation.csv", "statement_status", "document_status"),
            ("filing_value_reconciliation.csv", "value_status", "status"),
            ("financial_comparability.csv", "comparability_status", "status"),
        )
        for filename, label, field in layers:
            with (review_dir / filename).open(newline="", encoding="utf-8") as stream:
                for row in csv.DictReader(stream):
                    identity = (row["symbol"].strip().upper(), row.get("period_end", ""))
                    reconciliation.setdefault(identity, {})[label] = row[field]
    for item in outcomes:
        identity = (item["symbol"], item["period_end"])
        evidence = reconciliation.get(identity, {})
        item["reconciliation"] = evidence
        item["financial_values_verified"] = False
        item["ready_for_trading_signals"] = False
        item["reconciliation_status"] = (
            "DOCUMENT_AND_VALUES_MATCH_UNCERTIFIED"
            if item["acquisition_status"] == "ACQUIRED_UNVERIFIED"
            and evidence.get("document_status") == "REVIEW_ORIGINAL_DOCUMENT"
            and evidence.get("statement_status") == "MATCHED_DOCUMENT_UNCERTIFIED"
            and evidence.get("value_status") == "VALUES_MATCH_UNVERIFIED_TRANSCRIPTION"
            and evidence.get("comparability_status") == "CANDIDATE_COMPARABLE_UNVERIFIED"
            else "REVIEW_REQUIRED"
        )
    result = {"candidate_count": len(outcomes), "registered": bridge["registered"],
              "status_counts": dict(Counter(x["acquisition_status"] for x in outcomes)),
              "review": outcomes, "audit": audit, "certified": False,
              "ready_for_trading_signals": False}
    (out / "shortlist_financial_audit_summary.json").write_text(
        json.dumps(result, indent=2), encoding="utf-8")
    return result
