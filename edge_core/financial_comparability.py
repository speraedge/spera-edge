"""Conservative financial period comparability review.

Produces candidate arithmetic only. Even comparable-looking records cannot
be certified without verified original filings, restatements and publication
dates. No figures from this module may automatically become trading signals.
"""
import csv
import json
from collections import Counter, defaultdict
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path


def _prior_period(period_end, period_type):
    current = date.fromisoformat(period_end)
    if period_type == "FY":
        return current.replace(year=current.year - 1).isoformat()
    if period_type == "Q":
        year = current.year - (current.month <= 3)
        month = ((current.month - 4) % 12) + 1
        from calendar import monthrange
        current_is_month_end = current.day == monthrange(current.year, current.month)[1]
        day = monthrange(year, month)[1] if current_is_month_end else min(current.day, monthrange(year, month)[1])
        return date(year, month, day).isoformat()
    raise ValueError("Unsupported period type")


def review_comparability(financials_csv, output_dir):
    path = Path(financials_csv)
    required = {"symbol", "isin", "period_end", "period_type", "basis",
                "revenue", "pat", "source_url", "published_on"}
    with path.open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        if not reader.fieldnames or not required.issubset(reader.fieldnames):
            raise ValueError("Missing financial statement columns")
        records = list(reader)
    groups = defaultdict(list)
    for line, record in enumerate(records, 2):
        key = (str(record["isin"]).strip().upper(), str(record["period_type"]).strip().upper(),
               str(record["basis"]).strip().upper(), str(record["period_end"]).strip())
        groups[key].append((line, record))
    findings = []
    for line, record in enumerate(records, 2):
        isin, kind, basis, period = (str(record["isin"]).strip().upper(),
                                     str(record["period_type"]).strip().upper(),
                                     str(record["basis"]).strip().upper(),
                                     str(record["period_end"]).strip())
        status = "UNVERIFIED_SOURCE"
        previous = ""
        revenue_growth = ""
        pat_growth = ""
        try:
            previous = _prior_period(period, kind)
            current_published = date.fromisoformat(str(record["published_on"]))
            current_revenue = Decimal(str(record["revenue"]))
            current_pat = Decimal(str(record["pat"]))
            current_key = (isin, kind, basis, period)
            previous_key = (isin, kind, basis, previous)
            if len(groups[current_key]) != 1:
                status = "DUPLICATE_CURRENT_PERIOD"
            elif len(groups[previous_key]) != 1:
                status = "MISSING_OR_DUPLICATE_PRIOR_PERIOD"
            else:
                earlier = groups[previous_key][0][1]
                earlier_published = date.fromisoformat(str(earlier["published_on"]))
                earlier_revenue = Decimal(str(earlier["revenue"]))
                earlier_pat = Decimal(str(earlier["pat"]))
                if (current_published < date.fromisoformat(period)
                    or earlier_published < date.fromisoformat(previous)
                    or current_published > date.today()
                    or earlier_published > date.today()
                    or earlier_published > current_published):
                    status = "INVALID_PUBLICATION_DATE"
                elif (not all(v.is_finite() for v in
                              (current_revenue, current_pat, earlier_revenue, earlier_pat))
                      or current_revenue < 0 or earlier_revenue <= 0):
                    status = "INVALID_FINANCIAL_VALUES"
                elif (not str(record["source_url"]).startswith("https://")
                      or not str(earlier["source_url"]).startswith("https://")):
                    status = "MISSING_SOURCE"
                else:
                    revenue_growth = str((current_revenue / earlier_revenue - 1) * 100)
                    if earlier_pat != 0:
                        pat_growth = str((current_pat / abs(earlier_pat) - (1 if earlier_pat > 0 else -1)) * 100)
                    status = "CANDIDATE_COMPARABLE_UNVERIFIED"
        except (ValueError, InvalidOperation, OverflowError):
            status = "INVALID_PERIOD_OR_VALUES"
        findings.append({"row": line, "symbol": record["symbol"], "isin": isin,
                         "period_type": kind, "basis": basis, "period_end": period,
                         "prior_period_end": previous, "status": status,
                         "revenue_growth_candidate_pct": revenue_growth,
                         "pat_growth_candidate_pct": pat_growth, "certified": False})
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    fields = ["row", "symbol", "isin", "period_type", "basis", "period_end",
              "prior_period_end", "status", "revenue_growth_candidate_pct",
              "pat_growth_candidate_pct", "certified"]
    with (out / "financial_comparability.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(findings)
    summary = {"rows": len(findings),
               "status_counts": dict(Counter(item["status"] for item in findings)),
               "certified_growth_rows": 0, "certified": False}
    (out / "financial_comparability_summary.json").write_text(json.dumps(summary, indent=2))
    return summary
