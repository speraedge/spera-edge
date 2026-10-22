"""Download explicitly identified exchange filing attachments with provenance.

No exchange scraping or inferred filing identifiers. A download is quarantined
until issuer, reporting basis, values, and point-in-time availability are checked.
"""
import argparse
import csv
import hashlib
import json
from pathlib import Path
from urllib.parse import urlparse

import requests

ALLOWED_HOSTS = {"nseindia.com", "www.nseindia.com", "archives.nseindia.com",
                 "nsearchives.nseindia.com", "bseindia.com", "www.bseindia.com",
                 "www.bseindia.com", "corporates.bseindia.com"}
MAX_BYTES = 25 * 1024 * 1024


def validate_url(url):
    parsed = urlparse(str(url).strip())
    if parsed.scheme != "https" or parsed.hostname not in ALLOWED_HOSTS:
        raise ValueError("Source must be an explicitly allowed official exchange HTTPS URL")
    if parsed.username or parsed.password or parsed.port or parsed.fragment:
        raise ValueError("Source URL cannot include credentials or a port")
    return parsed.geturl()


def acquire(register_csv, output_dir, session=None):
    source = Path(register_csv)
    with source.open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        if not reader.fieldnames or not {"symbol", "isin", "period_end", "source_url"}.issubset(reader.fieldnames):
            raise ValueError("Source register requires symbol, isin, period_end, source_url")
        rows = list(reader)
    destination = Path(output_dir)
    destination.mkdir(parents=True, exist_ok=True)
    client = session or requests.Session()
    findings = []
    for number, item in enumerate(rows, 2):
        result = {"row": number, "symbol": item["symbol"], "isin": item["isin"],
                  "period_end": item["period_end"], "source_url": item["source_url"],
                  "file": "", "sha256": "", "bytes": 0, "status": "NOT_ACQUIRED",
                  "certified": False}
        try:
            url = validate_url(item["source_url"])
            with client.get(url, timeout=(10, 30), stream=True, allow_redirects=False,
                            headers={"User-Agent": "SPERA-EDGE-Evidence-Audit/1.0"}) as response:
                if response.status_code != 200:
                    result["status"] = "HTTP_" + str(response.status_code)
                else:
                    data = bytearray()
                    for chunk in response.iter_content(chunk_size=65536):
                        data.extend(chunk)
                        if len(data) > MAX_BYTES:
                            raise ValueError("Attachment exceeds size limit")
                    if not data.startswith(b"%PDF-"):
                        result["status"] = "UNSUPPORTED_OR_NON_PDF_RESPONSE"
                    else:
                        digest = hashlib.sha256(data).hexdigest()
                        filename = f"filing_{number}_{digest[:16]}.pdf"
                        (destination / filename).write_bytes(data)
                        result.update({"file": filename, "sha256": digest,
                                       "bytes": len(data), "status": "ACQUIRED_UNVERIFIED"})
        except (ValueError, requests.RequestException) as exc:
            result["status"] = "BLOCKED_" + type(exc).__name__
        findings.append(result)
    manifest = {"source_register_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
                "documents": findings, "certified": False, "ready_for_financial_growth": False}
    (destination / "acquisition_manifest.json").write_text(json.dumps(manifest, indent=2))
    return manifest


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--register", required=True)
    parser.add_argument("--output", default="data/filing_acquisition")
    args = parser.parse_args()
    result = acquire(args.register, args.output)
    print(json.dumps({"documents": len(result["documents"]),
                      "acquired": sum(x["status"] == "ACQUIRED_UNVERIFIED" for x in result["documents"]),
                      "certified": False}, indent=2))


if __name__ == "__main__":
    main()
