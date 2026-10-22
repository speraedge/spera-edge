"""Validate structured setup decisions independently of actual fills."""
from datetime import date

DECISIONS = ('WATCH', 'TAKE', 'REJECT', 'MISSED')
REASONS = ('SETUP_QUALITY', 'VOLUME', 'MARKET_REGIME', 'RISK', 'TIMING', 'OTHER')

def validate_decision(symbol, session, decision, reason, note):
    symbol = str(symbol).strip().upper()
    if not symbol or len(symbol) > 40 or not symbol.replace('-', '').replace('.', '').isalnum():
        raise ValueError('Invalid symbol')
    session = date.fromisoformat(str(session))
    if session > date.today():
        raise ValueError('Future session not permitted')
    if decision not in DECISIONS or reason not in REASONS:
        raise ValueError('Invalid decision classification')
    note = str(note).strip()
    if not note or len(note) > 3000:
        raise ValueError('A rationale is required, maximum 3000 characters')
    return dict(symbol=symbol, session=session.isoformat(), decision=decision, reason=reason, note=note)
