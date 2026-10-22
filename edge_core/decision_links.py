"""Explicit private links between setup decisions and recorded BUY events."""

def validate_trade_link(decisions, events, decision_id, event_id):
    decision = next((d for d in decisions if d.get('decision_id') == decision_id), None)
    event = next((e for e in events if e.get('event_id') == event_id), None)
    if decision is None or event is None:
        raise ValueError('Decision and trade must both exist in this private ledger')
    if decision.get('decision') != 'TAKE' or event.get('kind') != 'BUY':
        raise ValueError('Only TAKE decisions can link to recorded BUY events')
    if decision.get('symbol') != event.get('symbol'):
        raise ValueError('Decision and trade symbols differ')
    return {'decision_id': decision_id, 'event_id': event_id, 'symbol': decision['symbol']}
