import pandas as pd
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

def _get_last_expected_trading_day(now_ist: datetime):
    """
    Determines the date of the most recently completed trading session.
    Since the workflow runs on Friday and Saturday nights, we accept Friday's 
    data as the latest valid session until Monday evening.
    """
    current_date = now_ist.date()
    weekday = current_date.weekday() # 0=Mon, 4=Fri, 5=Sat, 6=Sun
    current_time = now_ist.time()
    
    # NSE market closes at 15:30 IST. We use 16:00 IST as the cutoff for data availability.
    market_closed_today = current_time >= time(16, 0)
    
    if weekday == 5: # Saturday
        return current_date - timedelta(days=1) # Expecting Friday
    if weekday == 6: # Sunday
        return current_date - timedelta(days=2) # Expecting Friday
    if weekday == 0: # Monday
        if market_closed_today:
            return current_date # Expecting Monday
        else:
            return current_date - timedelta(days=3) # Expecting Friday
    # Tuesday - Friday
    if market_closed_today:
        return current_date
    else:
        return current_date - timedelta(days=1)

def snapshot_is_fresh(last_session_date, now_ist_datetime) -> bool:
    """
    Returns True if the snapshot matches the most recently expected trading day.
    """
    if isinstance(last_session_date, str):
        last_session_date = pd.to_datetime(last_session_date).date()
    
    if isinstance(now_ist_datetime, str):
        now_ist_datetime = pd.to_datetime(now_ist_datetime)
        if now_ist_datetime.tzinfo is None:
            now_ist_datetime = now_ist_datetime.replace(tzinfo=ZoneInfo("Asia/Kolkata"))
            
    expected_date = _get_last_expected_trading_day(now_ist_datetime)
    
    return last_session_date == expected_date
