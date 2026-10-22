"""Explicit, read-only Upstox historical snapshot; fail closed on missing inputs."""
import argparse
import json
import os
from pathlib import Path
import pandas as pd
from edge_core.upstox import fetch_daily_candles

def build(mapping, start, end, outdir, token):
    if not mapping or len(mapping) != len(set(mapping)):
        raise ValueError("Provide a nonempty, unique symbol-to-instrument mapping.")
    # Validate the complete mapping before any provider request or output write.
    normalized = [str(symbol).strip().upper() for symbol in mapping]
    if len(set(normalized)) != len(normalized):
        raise ValueError("Duplicate symbols after normalization")
    if any(not symbol.replace("_", "").isalnum() for symbol in normalized):
        raise ValueError("Invalid symbol in mapping")
    out = Path(outdir)
    out.mkdir(parents=True, exist_ok=True)
    frames = {}
    coverage = {}
    for symbol, instrument in mapping.items():
        symbol = str(symbol).strip().upper()
        if not symbol.replace("_", "").isalnum() or not instrument:
            raise ValueError("Invalid symbol or instrument key.")
        candles = fetch_daily_candles(instrument, start, end, token=token)
        if candles.empty:
            coverage[symbol] = {"rows": 0, "status": "NO_DATA"}
            continue
        frame = candles.copy()
        frame.index = pd.to_datetime(frame.index)
        frames[symbol] = frame
        coverage[symbol] = {"rows": len(frame), "latest": str(frame.index.max().date()), "status": "RESEARCH_ONLY"}
    if not frames or len(frames) != len(mapping):
        raise ValueError("Incomplete provider coverage; snapshot publication refused")
    for field in ("open", "high", "low", "close", "volume"):
        wide = pd.DataFrame({f"{symbol}.NS": frame[field] for symbol, frame in frames.items()})
        wide.index.name = "Date"
        wide.to_csv(out / f"{field}.csv")
    (out / "metadata.json").write_text(json.dumps({
        "source": "Upstox historical-candle API",
        "requested_start": start, "requested_end": end,
        "universe_coverage": coverage,
        "quality": "UNVERIFIED_CORPORATE_ACTIONS",
        "rank_certification": False,
    }, indent=2))
    return coverage

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--mapping", required=True, help="JSON object SYMBOL: Upstox instrument key")
    parser.add_argument("--start", required=True)
    parser.add_argument("--end", required=True)
    parser.add_argument("--outdir", default="snapshot")
    args = parser.parse_args()
    mapping = json.loads(args.mapping)
    if not isinstance(mapping, dict):
        raise ValueError("Mapping must be a JSON object.")
    token = os.environ.get("UPSTOX_ACCESS_TOKEN")
    if not token:
        raise RuntimeError("UPSTOX_ACCESS_TOKEN secret is required.")
    coverage = build(mapping, args.start, args.end, args.outdir, token)
    print(f"Completed read-only historical retrieval for {len(coverage)} mapped symbols.")

if __name__ == "__main__":
    main()
