"""Validate EDGE replay against repository's saved Upstox OHLCV snapshot.

Research-only smoke check; no API calls, no orders, no performance certification.
"""
from pathlib import Path
import json
import pandas as pd
from edge_core.historical_replay import replay_breakout_rules


def run(root=Path("data/latest")):
    root = Path(root)
    meta = json.loads((root / "metadata.json").read_text())
    if meta.get("source", "").find("Upstox") < 0 or meta.get("universe") != "NIFTY_500":
        raise ValueError("Unexpected OHLCV source or universe")
    frames = {}
    for name in ("close", "high", "low", "volume"):
        frames[name] = pd.read_csv(root / (name + ".csv"), index_col="Date", parse_dates=["Date"]).sort_index()
    if any(not f.index.equals(frames["close"].index) or not f.columns.equals(frames["close"].columns) for f in frames.values()):
        raise ValueError("Saved OHLCV tables are misaligned")
    if len(frames["close"].columns) < 495:
        raise ValueError("Insufficient NIFTY 500 symbol coverage")
    if str(frames["close"].index[-1].date()) != meta["last_session"]:
        raise ValueError("Snapshot last session differs from metadata")
    result = replay_breakout_rules(frames["close"], frames["high"], frames["low"],
                                   frames["volume"], start=frames["close"].index[-60])
    if not result.empty and (not result["Outcome"].isin(
            ["SUCCESS", "FAILURE", "STOP_BREACH", "UNRESOLVED"]).all()
            or result[["Symbol", "Session"]].duplicated().any()):
        raise ValueError("Invalid replay outcomes or duplicated events")
    counts = result["Outcome"].value_counts()
    summary = {"universe": meta["universe"], "session": meta["last_session"],
               "symbols": len(frames["close"].columns), "replay_sessions": 60,
               "qualified": len(result), "resolved": int(counts.get("SUCCESS", 0)
                                                        + counts.get("FAILURE", 0)
                                                        + counts.get("STOP_BREACH", 0)),
               "successes": int(counts.get("SUCCESS", 0)),
               "stop_breaches": int(counts.get("STOP_BREACH", 0)),
               "unresolved": int(counts.get("UNRESOLVED", 0)),
               "quality": meta["quality"], "certified": False}
    print(json.dumps(summary, sort_keys=True))
    return summary


if __name__ == "__main__":
    run()
