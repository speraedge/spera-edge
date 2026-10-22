"""Publish dated official membership and independently identified benchmark evidence."""
from datetime import datetime, timezone, timedelta
from pathlib import Path
import gzip
import hashlib
import json
import os
import requests
from edge_core.momentum_universe import fetch_official_universe, NIFTY_500
from edge_core.instrument_mapping import UPSTOX_NSE_MASTER
from edge_core.upstox import fetch_daily_candles


def publish(directory='data/latest'):
    root = Path(directory)
    root.mkdir(parents=True, exist_ok=True)
    universe, industry = fetch_official_universe(NIFTY_500, attempts_per_url=1)
    if 'ISIN Code' not in universe.columns:
        raise ValueError('Official membership missing ISIN Code; evidence publication blocked')
    members = universe[['Symbol', 'ISIN Code', industry]].rename(columns={industry: 'Industry'})
    members['ISIN Code'] = members['ISIN Code'].fillna('').astype(str).str.strip().str.upper()
    if (members['ISIN Code'].eq('').any() or members['ISIN Code'].duplicated().any()):
        raise ValueError('Official membership contains missing or duplicate ISIN identities')
    members.to_csv(root / 'current_membership.csv', index=False)
    now = datetime.now(timezone.utc)
    evidence = {'fetched_utc': now.isoformat(), 'membership_source': universe.attrs['universe_source_url'],
                'membership_sha256': hashlib.sha256((root / 'current_membership.csv').read_bytes()).hexdigest(),
                'membership_rows': len(members), 'benchmark_status': 'UNAVAILABLE'}
    try:
        response = requests.get(UPSTOX_NSE_MASTER, timeout=40)
        response.raise_for_status()
        raw = response.content
        rows = json.loads(gzip.decompress(raw) if raw[:2] == b'\x1f\x8b' else raw)
        matching = [row for row in rows if row.get('segment') == 'NSE_INDEX' and str(row.get('name', '')).strip().lower() == 'nifty 500']
        if len(matching) != 1 or not matching[0]['instrument_key'].startswith('NSE_INDEX|'):
            raise ValueError('Ambiguous benchmark identity')
        token = os.getenv('UPSTOX_ACCESS_TOKEN') or os.getenv('UPSTOX_ANALYTIC_TOKEN')
        candles = fetch_daily_candles(matching[0]['instrument_key'], (now - timedelta(days=490)).date(), now.date(), token=token)
        if len(candles) < 253:
            raise ValueError('Insufficient benchmark history')
        candles.tail(253).to_csv(root / 'benchmark.csv', index_label='Date')
        evidence.update(benchmark_status='PROVIDER_HISTORY', benchmark_name='NIFTY 500',
                        benchmark_instrument=matching[0]['instrument_key'], benchmark_identity_source=UPSTOX_NSE_MASTER,
                        benchmark_sha256=hashlib.sha256((root / 'benchmark.csv').read_bytes()).hexdigest())
    except Exception as exc:
        evidence['benchmark_error_type'] = type(exc).__name__
    (root / 'evidence.json').write_text(json.dumps(evidence, indent=2))
    print(json.dumps(evidence, indent=2))


if __name__ == '__main__':
    publish()
