"""Validated, dated research fallback; never upgrades historical ranks to live signals."""
from pathlib import Path
import hashlib
import json
import pandas as pd

REQUIRED = {"Symbol", "Data_Quality", "Ret_6M", "Ret_12M", "AnnVol", "Percentile", "Pure_Momentum_Rank"}


def _valid(frame):
    if frame is None or len(frame) < 2 or not REQUIRED.issubset(frame.columns):
        return False
    if frame["Symbol"].isna().any() or frame["Symbol"].duplicated().any():
        return False
    if not frame["Data_Quality"].isin(["PASS", "REVIEW", "FAIL"]).all():
        return False
    return True


def load_leadership(latest_dir, history_dir, *, latest_date=None, current_date=None):
    latest_dir, history_dir = Path(latest_dir), Path(history_dir)
    path = latest_dir / "leadership.csv"
    if path.is_file():
        try:
            frame = pd.read_csv(path)
            if _valid(frame) and (current_date is None or str(latest_date) == str(current_date)):
                return frame, str(latest_date or "latest snapshot"), False
        except (OSError, ValueError, pd.errors.ParserError):
            pass
    manifest = history_dir / "manifest.json"
    if not manifest.is_file():
        return None, None, True
    try:
        metadata = json.loads(manifest.read_text())
        if metadata.get("universe") != "NIFTY_500":
            return None, None, True
        for entry in sorted(metadata.get("weeks", []), key=lambda x: x.get("weekly_key", ""), reverse=True):
            if latest_date and str(entry.get("weekly_key", "")) > str(latest_date):
                continue
            file = entry.get("file", "")
            if not file or Path(file).name != file or not file.endswith(".csv"):
                continue
            archive = history_dir / file
            if not archive.is_file() or hashlib.sha256(archive.read_bytes()).hexdigest() != entry.get("sha256"):
                continue
            try:
                frame = pd.read_csv(archive)
            except (OSError, ValueError, pd.errors.ParserError):
                continue
            # SPERA Wisdom historical export has Ticker instead of Symbol.
            if "Symbol" not in frame.columns and "Ticker" in frame.columns:
                frame = frame.rename(columns={"Ticker": "Symbol"})
            if "Data_Quality" not in frame.columns:
                continue
            if "AnnVol" not in frame.columns and "IVOL_Annualized" in frame.columns:
                frame["AnnVol"] = frame["IVOL_Annualized"]
            if _valid(frame):
                return frame, str(entry["weekly_key"]), True
    except (OSError, ValueError, KeyError, TypeError, pd.errors.ParserError):
        pass
    return None, None, True
