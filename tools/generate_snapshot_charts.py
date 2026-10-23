"""Phase 2 snapshot-bound research chart rendering; no private D1 access."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

import pandas as pd


def snapshot_key(metadata: dict) -> str:
    session = str(metadata.get("last_session", ""))
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", session):
        raise ValueError("Snapshot requires a valid last_session")
    fingerprint = hashlib.sha256(json.dumps(metadata, sort_keys=True).encode()).hexdigest()[:12]
    return f"{session}-{fingerprint}"


def generate_charts(snapshot_dir=Path("data/latest"), output_root=Path("artifacts/charts")):
    """Generate only public OHLCV research charts in a snapshot-specific directory.

    Generated PNGs are ignored by Git. No private database or manual fundamentals
    are read. A failed render leaves the prior current pointer untouched.
    """
    from edge_core.snapshot_integrity import validate_snapshot
    validate_snapshot(Path(snapshot_dir))
    snapshot_dir, output_root = Path(snapshot_dir), Path(output_root)
    metadata = json.loads((snapshot_dir / "metadata.json").read_text())
    if metadata.get("universe") != "NIFTY_500":
        raise ValueError("Unexpected universe")
    key = snapshot_key(metadata)
    target = output_root / key
    target.mkdir(parents=True, exist_ok=True)
    close = pd.read_csv(snapshot_dir / "close.csv", index_col="Date", parse_dates=["Date"])
    if close.empty or len(close.columns) < 495:
        raise ValueError("Insufficient validated close history")
    # Matplotlib is imported lazily, only for chart generation.
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    breadth = close.gt(close.rolling(50, min_periods=50).mean()).sum(axis=1)
    eligible = close.rolling(50, min_periods=50).count().ge(50).sum(axis=1)
    pct = (100 * breadth / eligible.where(eligible.ne(0))).dropna()
    if pct.empty:
        raise ValueError("Insufficient history for 50-session breadth chart")
    fig, ax = plt.subplots(figsize=(11, 4))
    ax.plot(pct.index, pct.values, label="Above 50-session mean (%)")
    ax.set(title="SPERA EDGE · 50-session market participation", ylabel="Percent", ylim=(0, 100))
    ax.grid(alpha=0.2)
    ax.legend(loc="best")
    fig.tight_layout()
    chart_path = target / "market_breadth_50.png"
    fig.savefig(chart_path, dpi=120)
    plt.close(fig)
    manifest = {
        "snapshot_key": key, "last_session": metadata["last_session"],
        "research_only": True, "certified": False,
        "charts": {"market_breadth_50.png": hashlib.sha256(chart_path.read_bytes()).hexdigest()},
    }
    (target / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    # Atomic pointer update; no deletion of older snapshots without external retention policy.
    output_root.mkdir(parents=True, exist_ok=True)
    pointer = output_root / "current.json"
    pending = output_root / "current.json.tmp"
    pending.write_text(json.dumps({"snapshot_key": key}, sort_keys=True) + "\n")
    pending.replace(pointer)
    return manifest


if __name__ == "__main__":
    print(json.dumps(generate_charts(), sort_keys=True))
