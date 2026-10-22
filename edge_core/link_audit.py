"""Read-only consistency checks for explicit private decision-to-trade links."""
import pandas as pd


def audit_decision_links(decisions, events, links):
    decision_by_id = {d['decision_id']: d for d in decisions}
    event_by_id = {e['event_id']: e for e in events}
    rows = []
    linked_events = set()
    for link in links:
        did, eid = link['decision_id'], link['event_id']
        decision, event = decision_by_id.get(did), event_by_id.get(eid)
        if eid in linked_events:
            status = 'DUPLICATE_BUY_LINK'
        elif decision is None or event is None:
            status = 'MISSING_REFERENCED_RECORD'
        elif decision.get('decision') != 'TAKE' or event.get('kind') != 'BUY':
            status = 'INVALID_RECORD_TYPE'
        elif decision.get('symbol') != event.get('symbol'):
            status = 'SYMBOL_MISMATCH'
        else:
            status = 'VALID'
        linked_events.add(eid)
        rows.append({'Decision_ID': did, 'Event_ID': eid, 'Symbol': event.get('symbol') if event else None, 'Status': status})
    for event in events:
        if event.get('kind') == 'BUY' and event['event_id'] not in linked_events:
            rows.append({'Decision_ID': None, 'Event_ID': event['event_id'], 'Symbol': event.get('symbol'), 'Status': 'UNLINKED_BUY'})
    return pd.DataFrame(rows, columns=['Decision_ID', 'Event_ID', 'Symbol', 'Status'])
