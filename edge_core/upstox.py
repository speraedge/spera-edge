"""Read-only Upstox daily history adapter. No token exchange or order endpoints."""
import os
from datetime import timedelta
from urllib.parse import quote
import pandas as pd
import requests

BASE_URL = "https://api.upstox.com/v2"

class UpstoxDataError(RuntimeError):
    pass

def fetch_daily_candles(instrument_key, start_date, end_date, token=None, session=None):
    """Fetch one instrument's daily OHLCV from Upstox historical-candle v2.
    
    Date arguments are YYYY-MM-DD. Tokens are never logged or stored.
    Returns a Date-indexed frame. Does not certify corporate actions or freshness.
    """
    token = token or os.getenv("UPSTOX_ACCESS_TOKEN")
    if not token:
        raise UpstoxDataError("UPSTOX_ACCESS_TOKEN is missing or expired.")
    if not instrument_key or not str(instrument_key).strip():
        raise ValueError("An Upstox instrument key is required.")
    start = pd.Timestamp(start_date).date()
    end = pd.Timestamp(end_date).date()
    if start > end:
        raise ValueError("Start date must not exceed end date.")
    key = quote(str(instrument_key), safe="")
    client = session or requests
    rows = []
    # Bound each daily request to <=350 calendar days; concatenate without
    # overlap so long-window requests work with provider per-call limits.
    cursor = start
    while cursor <= end:
        chunk_end = min(end, cursor + timedelta(days=349))
        url = f"{BASE_URL}/historical-candle/{key}/day/{chunk_end.isoformat()}/{cursor.isoformat()}"
        try:
            response = client.get(url, headers={"Authorization": f"Bearer {token}", "Accept": "application/json"}, timeout=30)
            response.raise_for_status()
            payload = response.json()
        except (requests.RequestException, ValueError) as exc:
            raise UpstoxDataError("Upstox historical request failed; verify token, instrument and date range.") from exc
        if payload.get("status") != "success":
            raise UpstoxDataError("Upstox did not return a successful historical response.")
        rows.extend((payload.get("data") or {}).get("candles") or [])
        cursor = chunk_end + timedelta(days=1)
    if not rows:
        return pd.DataFrame(columns=["open", "high", "low", "close", "volume"])
    if any(len(row) < 6 for row in rows):
        raise UpstoxDataError("Malformed Upstox candle response.")
    frame = pd.DataFrame([row[:6] for row in rows], columns=["date", "open", "high", "low", "close", "volume"])
    frame["date"] = pd.to_datetime(frame["date"], utc=True).dt.tz_convert("Asia/Kolkata").dt.date
    if frame["date"].duplicated().any():
        raise UpstoxDataError("Duplicate trading sessions in provider response.")
    for field in ("open", "high", "low", "close", "volume"):
        frame[field] = pd.to_numeric(frame[field], errors="coerce")
    if frame[["open", "high", "low", "close", "volume"]].isna().any().any():
        raise UpstoxDataError("Non-numeric OHLCV returned by provider.")
    return frame.set_index("date").sort_index()


def fetch_intraday_daily_candle(instrument_key, session_date, token=None, session=None):
    """Fetch one *provisional* Upstox V3 day candle, never a certified EOD."""
    token = token or os.getenv("UPSTOX_ACCESS_TOKEN")
    if not token:
        raise UpstoxDataError("UPSTOX_ACCESS_TOKEN is missing or expired.")
    key = quote(str(instrument_key), safe="")
    url = f"https://api.upstox.com/v3/historical-candle/intraday/{key}/days/1"
    try:
        response = (session or requests).get(
            url, headers={"Authorization": f"Bearer {token}", "Accept": "application/json"},
            timeout=30)
        response.raise_for_status()
        payload = response.json()
    except (requests.RequestException, ValueError) as exc:
        raise UpstoxDataError("Upstox V3 provisional daily request failed.") from exc
    if payload.get("status") != "success":
        raise UpstoxDataError("Upstox V3 provisional daily response unsuccessful.")
    rows = (payload.get("data") or {}).get("candles") or []
    if any(len(row) < 6 for row in rows):
        raise UpstoxDataError("Malformed V3 provisional candle.")
    if not rows:
        raise UpstoxDataError("No V3 provisional candle available.")
    frame = pd.DataFrame([row[:6] for row in rows],
                         columns=["timestamp", "open", "high", "low", "close", "volume"])
    timestamps = pd.to_datetime(frame["timestamp"], utc=True, errors="coerce")
    if timestamps.isna().any():
        raise UpstoxDataError("Invalid V3 candle timestamp.")
    frame["date"] = timestamps.dt.tz_convert("Asia/Kolkata").dt.date
    target = pd.Timestamp(session_date).date()
    if len(frame) != 1 or frame["date"].iloc[0] != target:
        raise UpstoxDataError("V3 provisional candle is missing, duplicated or not for requested IST session.")
    for field in ("open", "high", "low", "close", "volume"):
        frame[field] = pd.to_numeric(frame[field], errors="coerce")
    o, h, lo, c, v = (float(frame[field].iloc[0]) for field in
                      ("open", "high", "low", "close", "volume"))
    import math
    if not all(map(math.isfinite, (o, h, lo, c, v))) or min(o, h, lo, c) <= 0 or v < 0 or h < max(o, c, lo) or lo > min(o, c):
        raise UpstoxDataError("Invalid V3 provisional OHLCV candle.")
    return frame.set_index("date")[["open", "high", "low", "close", "volume"]]


def reconcile_provisional_daily(history, provisional, session_date):
    """Replace only the target session; never mutate caller's verified history."""
    target = pd.Timestamp(session_date).date()
    if history.index.has_duplicates or provisional.index.has_duplicates:
        raise UpstoxDataError("Duplicate provider session dates.")
    if len(provisional) != 1 or provisional.index[0] != target:
        raise UpstoxDataError("Provisional candle does not match requested session.")
    if any(pd.Timestamp(day).date() > target for day in history.index):
        raise UpstoxDataError("Historical response includes a future session.")
    result = history.copy()
    result.index = pd.Index([pd.Timestamp(day).date() for day in result.index])
    result = result.drop(index=target, errors="ignore")
    return pd.concat([result, provisional]).sort_index()
