"""Read-only Upstox daily history adapter. No token exchange or order endpoints."""
import os
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
    url = f"{BASE_URL}/historical-candle/{key}/day/{end.isoformat()}/{start.isoformat()}"
    client = session or requests
    try:
        response = client.get(url, headers={"Authorization": f"Bearer {token}", "Accept": "application/json"}, timeout=30)
        response.raise_for_status()
        payload = response.json()
    except (requests.RequestException, ValueError) as exc:
        raise UpstoxDataError("Upstox historical request failed; verify token, instrument and date range.") from exc
    if payload.get("status") != "success":
        raise UpstoxDataError("Upstox did not return a successful historical response.")
    rows = (payload.get("data") or {}).get("candles") or []
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
