"""EDGE research diagnostics and owner-scoped, append-only trade accounting."""
from datetime import datetime, timezone
import hashlib
import json
import math
import uuid
import numpy as np
import pandas as pd
from edge_exports import numbered, export_section
from edge_core.portfolio import position_size
from edge_core.portfolio_risk import risk_budget
from edge_core.trade_review import journal_quality


def market_report(close):
    prices = close.apply(pd.to_numeric, errors='coerce').replace([np.inf, -np.inf], np.nan)
    prices = prices.where(prices > 0)
    if prices.empty or prices.index.has_duplicates or not prices.index.is_monotonic_increasing:
        raise ValueError('Unique sorted market sessions required')
    breadth = pd.DataFrame(index=prices.index)
    for window in (50, 200):
        average = prices.rolling(window, min_periods=window).mean()
        eligible = average.notna() & prices.notna()
        breadth[f'Above_{window}_Pct'] = 100 * (prices.gt(average) & eligible).sum(axis=1) / eligible.sum(axis=1).replace(0, np.nan)
        breadth[f'Coverage_{window}'] = eligible.sum(axis=1)
    daily = prices.pct_change(fill_method=None)
    latest = daily.iloc[-1].dropna()
    change = breadth['Above_50_Pct'].diff(20).iloc[-1]
    short = breadth['Above_50_Pct'].iloc[-1]
    long = breadth['Above_200_Pct'].iloc[-1]
    condition = 'INSUFFICIENT_COVERAGE'
    if breadth['Coverage_200'].iloc[-1] >= 0.9 * len(prices.columns) and pd.notna(short):
        condition = 'DEFENSIVE' if short < 40 or long < 40 else ('BROAD_PARTICIPATION' if short >= 60 and long >= 60 else 'MIXED')
    return {'latest_coverage': int(prices.iloc[-1].notna().sum()),
            'advances': int((latest > 0).sum()), 'declines': int((latest < 0).sum()),
            'unchanged': int((latest == 0).sum()), 'comparison_coverage': len(latest),
            'breadth_change_20_pp': None if pd.isna(change) else float(change),
            'condition': condition, 'history': breadth.tail(126)}


def entry_diagnostics(close, high, low, volume, as_of):
    frames = (close, high, low, volume)
    if any(not frame.index.equals(close.index) or not frame.columns.equals(close.columns) for frame in frames):
        raise ValueError('OHLCV must have identical sessions and symbols')
    if close.index.has_duplicates or close.columns.has_duplicates or not close.index.is_monotonic_increasing:
        raise ValueError('Unique sorted OHLCV identities required')
    selected = [frame.loc[frame.index <= pd.Timestamp(as_of)].tail(61) for frame in frames]
    records = []
    for symbol in close:
        record = {'Symbol': symbol, 'Evidence': 'INCOMPLETE_OHLCV', 'SEPA_Certified': False}
        sample = pd.DataFrame({name: frame[symbol] for name, frame in zip(('close', 'high', 'low', 'volume'), selected)})
        sample = sample.apply(pd.to_numeric, errors='coerce')
        valid = np.isfinite(sample).all(axis=1) & sample[['close', 'high', 'low']].gt(0).all(axis=1)
        valid &= sample['high'].ge(sample['close']) & sample['low'].le(sample['close']) & sample['volume'].ge(0)
        if len(sample) < 61 or not valid.all():
            records.append(record)
            continue
        prior = sample.iloc[:-1]
        today = sample.iloc[-1]
        pivot = float(prior['high'].tail(20).max())
        stop = float(prior['low'].tail(10).min())
        baseline = float(prior['volume'].tail(50).mean())
        ratio = float(today['volume'] / baseline) if baseline > 0 else np.nan
        blocks = (prior.iloc[-35:-15], prior.iloc[-15:-5], prior.iloc[-5:])
        ranges = [float((block['high'].max() - block['low'].min()) / block['high'].max()) for block in blocks]
        contraction = ranges[0] > ranges[1] > ranges[2] and ranges[2] <= 0.08
        record.update(Evidence='COMPLETED_SESSION_RESEARCH', Session=str(sample.index[-1].date()),
                      Pivot=pivot, Stop=stop, Close=float(today['close']), Volume_Ratio=ratio,
                      Price_Breakout=bool(today['close'] > pivot), Volume_Confirmed=bool(ratio >= 1.5),
                      VCP_Contraction=bool(contraction), Range_First=ranges[0], Range_Second=ranges[1], Range_Final=ranges[2],
                      Entry_Extended=bool(today['close'] > pivot * 1.05),
                      Technical_Entry_Review=bool(contraction and today['close'] > pivot and ratio >= 1.5 and today['close'] <= pivot * 1.05 and stop < today['close']))
        records.append(record)
    return pd.DataFrame(records)


def plan_quantity(equity, risk_pct, entry, stop, committed_risk, exposure, heat_pct=5, exposure_pct=100, single_pct=10):
    values = (exposure, exposure_pct, single_pct)
    if not all(math.isfinite(float(value)) for value in values) or exposure < 0 or not 0 < exposure_pct <= 100 or not 0 < single_pct <= 100:
        raise ValueError('Invalid exposure limits')
    sizing = position_size(equity, risk_pct, entry, stop)
    budget = risk_budget(equity, risk_pct, committed_risk, heat_pct)
    notional_capacity = max(0, min(equity * exposure_pct / 100 - exposure, equity * single_pct / 100))
    quantity = min(sizing['quantity'], math.floor(budget['new_trade_budget'] / sizing['risk_per_share']), math.floor(notional_capacity / entry))
    return {'quantity': quantity, 'planned_risk': quantity * sizing['risk_per_share'], 'notional': quantity * entry,
            'available_risk': budget['available_risk'], 'notional_capacity': notional_capacity}


def identity_owner(identity, allowed_emails):
    email = str(identity.get('email', '')).strip().lower()
    if identity.get('email_verified') is not True or not identity.get('sub') or not identity.get('iss') or email not in {str(item).strip().lower() for item in allowed_emails}:
        raise ValueError('A verified, allowlisted OIDC identity is required')
    return hashlib.sha256((str(identity['iss']) + '\0' + str(identity['sub'])).encode()).hexdigest()


def industry_participation(close, members):
    if not {'Symbol', 'Industry'}.issubset(members.columns) or members['Symbol'].duplicated().any() or members[['Symbol', 'Industry']].isna().any().any():
        raise ValueError('Unique official industry membership required')
    if len(close) < 64:
        raise ValueError('At least 64 price sessions required')
    prices = close.apply(pd.to_numeric, errors='coerce').replace([np.inf, -np.inf], np.nan).where(lambda frame: frame > 0)
    valid = prices.tail(64).notna().all()
    returns = (prices.iloc[-1] / prices.iloc[-64] - 1).where(valid)
    trend = prices.iloc[-1].gt(prices.tail(50).mean()).where(valid)
    out = members.copy()
    out['Return_63D'] = out['Symbol'].map(returns)
    out['Above50'] = out['Symbol'].map(trend)
    grouped = out.groupby('Industry').agg(Members=('Symbol', 'size'), Price_Coverage=('Return_63D', 'count'), Median_Return_63D=('Return_63D', 'median'), Above_50_Pct=('Above50', 'mean')).reset_index()
    grouped['Above_50_Pct'] *= 100
    grouped['Rank'] = grouped['Median_Return_63D'].rank(ascending=False, method='min')
    return grouped.sort_values('Rank', na_position='last')


def load_current_evidence(directory, close):
    from pathlib import Path
    root = Path(directory)
    evidence = json.loads((root / 'evidence.json').read_text())
    fetched = datetime.fromisoformat(evidence['fetched_utc'])
    age = (datetime.now(timezone.utc) - fetched).total_seconds()
    if not 0 <= age <= 7 * 86400 or evidence['membership_source'] not in NIFTY_MEMBERSHIP_SOURCES:
        raise ValueError('Current membership evidence is stale or source is not authoritative')
    if hashlib.sha256((root / 'current_membership.csv').read_bytes()).hexdigest() != evidence['membership_sha256']:
        raise ValueError('Membership checksum mismatch')
    members = pd.read_csv(root / 'current_membership.csv')
    if len(members) != evidence['membership_rows'] or not 495 <= len(members) <= 505:
        raise ValueError('Membership coverage invalid')
    industries = industry_participation(close, members)
    benchmark = None
    if evidence.get('benchmark_status') == 'PROVIDER_HISTORY':
        if hashlib.sha256((root / 'benchmark.csv').read_bytes()).hexdigest() != evidence['benchmark_sha256']:
            raise ValueError('Benchmark checksum mismatch')
        frame = pd.read_csv(root / 'benchmark.csv', index_col='Date', parse_dates=['Date'])
        series = pd.to_numeric(frame['close'], errors='coerce').reindex(close.index)
        if len(series) >= 253 and np.isfinite(series.tail(253)).all() and series.tail(253).gt(0).all() and not frame.index.has_duplicates:
            benchmark = series
    return evidence, members, industries, benchmark


NIFTY_MEMBERSHIP_SOURCES = ('https://nsearchives.nseindia.com/content/indices/ind_nifty500list.csv', 'https://www.niftyindices.com/IndexConstituent/ind_nifty500list.csv')


class Ledger:
    def __init__(self, owner, query):
        if not owner:
            raise ValueError('Authenticated owner required')
        self.owner = owner
        self.query = query

    def initialize(self):
        self.query('''CREATE TABLE IF NOT EXISTS edge_trade_events (
            owner_id TEXT NOT NULL, event_id TEXT NOT NULL, revision INTEGER NOT NULL,
            created_utc TEXT NOT NULL, payload TEXT NOT NULL,
            PRIMARY KEY(owner_id,event_id), UNIQUE(owner_id,revision))''')

    def events(self):
        rows = self.query('SELECT event_id, revision, created_utc, payload FROM edge_trade_events WHERE owner_id=? ORDER BY revision', (self.owner,))
        return [dict(json.loads(row['payload']), event_id=row['event_id'], revision=row['revision'], created_utc=row['created_utc']) for row in rows]

    def append(self, kind, symbol, *, quantity=0, price=0, stop=0, fee=0, note='', event_id=None, expected_revision=None):
        events = self.events()
        event_id = event_id or str(uuid.uuid4())
        existing = next((event for event in events if event['event_id'] == event_id), None)
        payload = {'kind': kind, 'symbol': str(symbol).strip().upper(), 'quantity': quantity, 'price': price, 'stop': stop, 'fee': fee, 'note': str(note)}
        if existing:
            if any(existing.get(key) != value for key, value in payload.items()):
                raise ValueError('Submission ID already used for different contents')
            return event_id
        revision = len(events)
        if expected_revision is not None and revision != expected_revision:
            raise ValueError('Ledger changed in another session; refresh before recording')
        self._replay(events + [payload], {})
        rows = self.query('''INSERT INTO edge_trade_events(owner_id,event_id,revision,created_utc,payload)
            SELECT ?,?,?,?,? WHERE (SELECT COUNT(*) FROM edge_trade_events WHERE owner_id=?)=?
            RETURNING event_id''', (self.owner, event_id, revision + 1, datetime.now(timezone.utc).isoformat(), json.dumps(payload, allow_nan=False), self.owner, revision))
        if not rows:
            raise ValueError('Concurrent ledger update; refresh before recording')
        return event_id

    def report(self, marks):
        return self._replay(self.events(), marks)

    @staticmethod
    def _replay(events, marks):
        holdings = {}
        realized = 0.0
        for event in events:
            kind, symbol = event['kind'], event['symbol']
            if kind not in ('BUY', 'SELL', 'STOP', 'NOTE') or not symbol or len(symbol) > 40 or len(event['note']) > 10000:
                raise ValueError('Invalid transaction type, symbol, or note')
            quantity, price, stop, fee = (event[key] for key in ('quantity', 'price', 'stop', 'fee'))
            if not all(math.isfinite(float(value)) for value in (quantity, price, stop, fee)) or fee < 0:
                raise ValueError('Finite transaction values and nonnegative fees required')
            holding = holdings.setdefault(symbol, {'quantity': 0, 'cost': 0.0, 'stop': 0.0})
            if kind in ('BUY', 'SELL'):
                if isinstance(quantity, bool) or int(quantity) != quantity or quantity <= 0 or price <= 0:
                    raise ValueError('Positive whole quantity and price required')
                if kind == 'BUY':
                    if not 0 < stop < price:
                        raise ValueError('Initial long protective stop must be below purchase price')
                    holding['quantity'] += int(quantity)
                    holding['cost'] += quantity * price + fee
                    holding['stop'] = stop
                else:
                    if quantity > holding['quantity']:
                        raise ValueError('Exit exceeds recorded open quantity')
                    cost = holding['cost'] / holding['quantity'] * quantity
                    realized += quantity * price - fee - cost
                    holding['cost'] -= cost
                    holding['quantity'] -= int(quantity)
            elif kind == 'STOP':
                if holding['quantity'] <= 0 or stop <= 0:
                    raise ValueError('Stop update requires an open position and positive stop')
                holding['stop'] = stop
        rows = []
        for symbol, holding in holdings.items():
            quantity = holding['quantity']
            if quantity <= 0:
                continue
            mark = marks.get(symbol)
            valid = mark is not None and math.isfinite(float(mark)) and mark > 0
            rows.append({'Symbol': symbol, 'Quantity': quantity, 'Average_Cost': holding['cost'] / quantity,
                         'Stop': holding['stop'], 'Mark': mark if valid else None,
                         'Exposure': quantity * mark if valid else None,
                         'Unrealized': quantity * mark - holding['cost'] if valid else None,
                         'Open_Risk': quantity * max(0, mark - holding['stop']) if valid else None,
                         'Stop_Breached': bool(mark <= holding['stop']) if valid else None})
        positions = pd.DataFrame(rows, columns=['Symbol', 'Quantity', 'Average_Cost', 'Stop', 'Mark', 'Exposure', 'Unrealized', 'Open_Risk', 'Stop_Breached'])
        complete = positions.empty or positions['Mark'].notna().all()
        return positions, {'realized': realized,
                           'unrealized': float(positions['Unrealized'].sum()) if complete else None,
                           'exposure': float(positions['Exposure'].sum()) if complete else None,
                           'open_risk': float(positions['Open_Risk'].sum()) if complete else None,
                           'marks_complete': bool(complete)}


def render_market(close):
    import streamlit as st
    report = market_report(close)
    st.subheader('Market conditions and participation')
    st.write(f"Breadth condition: {report['condition']} (research heuristic)")
    st.caption('Defensive: either breadth below 40%; broad participation: both at least 60%; otherwise mixed. Requires 90% 200-session coverage. This is not a benchmark regime or a trading signal.')
    st.write({key: value for key, value in report.items() if key != 'history'})
    st.line_chart(report['history'][['Above_50_Pct', 'Above_200_Pct']])
    export_section('Market breadth history', report['history'].reset_index(), 'market_breadth_history')
    st.caption('20-session change measures breadth expansion/deterioration in percentage points. Historical breadth uses today’s available universe and has survivorship limitations.')


def leadership_evidence(levels, close, directory=None):
    from edge_core.institutional_momentum import compute_12_1_momentum, compute_path_quality
    out = levels.copy()
    momentum, paths = {}, {}
    if close is not None:
        for symbol in close:
            series = pd.to_numeric(close[symbol], errors='coerce')
            if len(series) >= 253 and np.isfinite(series.tail(253)).all() and series.tail(253).gt(0).all():
                momentum[symbol] = compute_12_1_momentum(series)
                paths[symbol] = compute_path_quality(series)['signed_r_squared']
    out['Institutional_12_1_Research'] = out['Symbol'].map(momentum)
    out['Signed_Path_Quality_Research'] = out['Symbol'].map(paths)
    out['Benchmark_RS_Gate'] = 'PENDING_AUTHORITATIVE_BENCHMARK'
    out['Current_Sector_Gate'] = 'PENDING_CURRENT_MEMBERSHIP'
    out['Fundamental_Gate'] = 'PENDING_VERIFIED_EARNINGS_SALES'
    out['Corporate_Action_Gate'] = 'PENDING_ADJUSTMENT_EVIDENCE'
    out['SEPA_Certified'] = False
    out['Research_Priority'] = pd.to_numeric(out.get('Percentile'), errors='coerce').where(out['Data_Quality'].isin(['PASS', 'REVIEW']))
    if directory is not None and close is not None:
        try:
            evidence, members, industries, benchmark = load_current_evidence(directory, close)
            out = out.merge(members, on='Symbol', how='left', validate='one_to_one')
            out = out.merge(industries[['Industry', 'Rank']], on='Industry', how='left', validate='many_to_one')
            out['Current_Sector_Gate'] = np.where(out['Industry'].notna(), 'DATED_OFFICIAL_INDUSTRY_RESEARCH', 'MISSING_MEMBERSHIP')
            out['Membership_Fetched_UTC'] = evidence['fetched_utc']
            if benchmark is not None:
                from edge_core.relative_strength import relative_strength
                relative = {}
                for symbol in close:
                    series = pd.to_numeric(close[symbol], errors='coerce')
                    if series.tail(253).notna().all() and series.tail(253).gt(0).all():
                        relative[symbol] = relative_strength(series, benchmark)['RS_252D']
                out['Benchmark_RS_252D'] = out['Symbol'].map(relative)
                out['Benchmark_RS_Gate'] = np.where(out['Benchmark_RS_252D'].notna(), 'COMPUTED_PROVIDER_BENCHMARK_RESEARCH', 'MISSING_ALIGNED_HISTORY')
        except (OSError, ValueError, KeyError, TypeError):
            pass
    return out


def render_industries(directory, close):
    import streamlit as st
    st.subheader('Current official industry participation')
    try:
        evidence, _, industries, _ = load_current_evidence(directory, close)
        st.caption(f"Official NSE membership fetched {evidence['fetched_utc']}; price session {close.index[-1].date()}. Equal-member research, not sector-index returns. Unknown classifications are not certified.")
        st.dataframe(numbered(industries), use_container_width=True)
        export_section('Industry research', industries, 'industry_research')
    except (OSError, ValueError, KeyError, TypeError):
        st.info('Current authoritative industry evidence unavailable. Archived sector rankings remain historical only.')


def render_entries(close, high, low, volume, last_session):
    import streamlit as st
    st.subheader('Completed-session pivots and volume confirmation')
    table = entry_diagnostics(close, high, low, volume, last_session)
    st.caption('Pivot: highest high of 20 prior sessions; volume: at least 1.5× prior 50-session mean. Stop: prior 10-session low. VCP diagnostic: shrinking disjoint 20/10/5-session ranges, final range ≤8%. These are research heuristics, not certified SEPA signals. Gaps and slippage can exceed stop risk.')
    st.dataframe(numbered(table), use_container_width=True)
    export_section('Entry diagnostics', table, 'entry_diagnostics')
    eligible = table.loc[table['Evidence'].eq('COMPLETED_SESSION_RESEARCH')]
    if not eligible.empty:
        watch = st.multiselect('Candidate watchlist', eligible['Symbol'].tolist())
        if watch:
            export_section('Selected watchlist', eligible[eligible['Symbol'].isin(watch)], 'selected_watchlist')
    st.subheader('Risk-based position plan')
    st.caption('Planning inputs only. Enter actual account equity, total marked exposure and total open mark-to-stop risk. Private ledger totals are available after sign-in on Portfolio & Journal.')
    equity = st.number_input('Planning equity (INR)', min_value=1.0, value=500000.0)
    risk = st.number_input('Planning risk per trade (%)', min_value=0.1, max_value=5.0, value=1.0)
    committed = st.number_input('Planning existing open risk (INR)', min_value=0.0, value=0.0)
    exposure = st.number_input('Planning current exposure (INR)', min_value=0.0, value=0.0)
    entry = st.number_input('Planned entry price', min_value=0.01, value=100.0)
    stop = st.number_input('Planned protective stop', min_value=0.01, value=95.0)
    try:
        st.write(plan_quantity(equity, risk, entry, stop, committed, exposure))
        st.caption('Caps: 5% aggregate open risk, 100% total exposure, 10% per new position. All values are planning assumptions; verify fills and available cash independently.')
    except ValueError as exc:
        st.error(str(exc))
    return table


def render_private_portfolio(close, snapshot_usable):
    import streamlit as st
    from edge_core.d1_store import d1_query
    st.caption('Private append-only trade accounting. Long positions only; entries record your actual fills and fees. No brokerage execution.')
    try:
        allowed = st.secrets.get('EDGE_JOURNAL_ALLOWED_EMAILS', [])
        auth_configured = 'auth' in st.secrets
    except FileNotFoundError:
        allowed, auth_configured = [], False
    if isinstance(allowed, str):
        allowed = [item.strip() for item in allowed.split(',')]
    if not allowed or not auth_configured:
        st.warning('Private ledger locked: configure Streamlit OIDC auth and EDGE_JOURNAL_ALLOWED_EMAILS. No private records are loaded.')
        return
    if not st.user.is_logged_in:
        if st.button('Sign in to private journal'):
            st.login()
        return
    try:
        owner = identity_owner(dict(st.user), allowed)
    except ValueError:
        st.error('This identity is not authorized for the private ledger.')
        if st.button('Sign out'):
            st.logout()
        return
    if st.button('Sign out of private journal'):
        st.logout()
    keys = ('EDGE_CF_ACCOUNT_ID', 'EDGE_D1_DATABASE_ID', 'EDGE_CF_API_TOKEN')
    credentials = {key: st.secrets.get(key) for key in keys}
    if not all(credentials.values()):
        st.error('EDGE D1 credentials are missing in Streamlit secrets. Private storage is unavailable.')
        return
    def query(sql, params=()):
        return d1_query(sql, params, account_id=credentials[keys[0]], database_id=credentials[keys[1]], token=credentials[keys[2]])
    try:
        ledger = Ledger(owner, query)
        ledger.initialize()
        events = ledger.events()
        st.subheader('Private journal completeness')
        quality = journal_quality(events)
        st.caption('Flags BUY entries without an accompanying entry note. A note is not proof of rule compliance; research signals are not matched to fills.')
        st.dataframe(numbered(quality), use_container_width=True)
        export_section('Private journal completeness', quality, 'private_journal_completeness')
        marks = close.iloc[-1].to_dict() if snapshot_usable and close is not None else {}
        positions, summary = ledger.report(marks)
        st.write(summary)
        st.dataframe(numbered(positions), use_container_width=True)
        export_section('Private positions', positions, 'private_positions')
        st.caption('Average-cost accounting includes entry/exit fees. Unrealized P&L excludes estimated exit costs. Open risk uses latest mark to stop, floored at zero; stops do not guarantee execution.')
        if not summary['marks_complete']:
            st.warning('Missing or stale marks: exposure, unrealized P&L and risk are unavailable. New-entry sizing is disabled.')
        capital = st.number_input('Account equity (INR)', min_value=1.0, value=500000.0)
        risk_pct = st.number_input('Permitted risk per trade (%)', min_value=0.1, max_value=5.0, value=1.0)
        heat = st.number_input('Portfolio risk ceiling (%)', min_value=0.1, max_value=10.0, value=5.0)
        exposure_limit = st.number_input('Gross exposure limit (%)', min_value=1.0, max_value=100.0, value=100.0)
        single_limit = st.number_input('Single position limit (%)', min_value=1.0, max_value=100.0, value=10.0)
        revision = len(events)
        if 'edge_event_id' not in st.session_state:
            st.session_state['edge_event_id'] = str(uuid.uuid4())
        with st.form('private_edge_event'):
            kind = st.selectbox('Record type', ['BUY', 'SELL', 'STOP', 'NOTE'])
            symbol = st.text_input('Recorded symbol').strip().upper()
            quantity = st.number_input('Filled quantity', min_value=1, value=1, step=1)
            price = st.number_input('Actual fill price', min_value=0.01, value=100.0)
            stop = st.number_input('Protective stop price', min_value=0.01, value=95.0)
            fee = st.number_input('Transaction fees (INR)', min_value=0.0, value=0.0)
            note = st.text_area('Private review note', max_chars=10000)
            submit = st.form_submit_button('Record private event')
        breached = not positions.empty and positions['Stop_Breached'].fillna(False).any()
        if breached:
            st.warning('A recorded protective stop is breached. Resolve the position before planning new entries.')
        if summary['marks_complete'] and snapshot_usable and not breached and kind == 'BUY' and stop < price:
            existing = positions.loc[positions['Symbol'].eq(symbol), 'Exposure'].sum() if not positions.empty else 0
            sizing = plan_quantity(capital, risk_pct, price, stop, summary['open_risk'], summary['exposure'], heat, exposure_limit, single_limit)
            remaining_single = max(0, capital * single_limit / 100 - existing)
            sizing['quantity'] = min(sizing['quantity'], math.floor(remaining_single / price))
            sizing['quantity'] = min(sizing['quantity'], max(0, math.floor((sizing['notional_capacity'] - fee) / price)), max(0, math.floor((min(capital * risk_pct / 100, sizing['available_risk']) - fee) / (price - stop))))
            sizing['planned_risk'] = sizing['quantity'] * (price - stop) + fee if sizing['quantity'] else 0
            sizing['notional'] = sizing['quantity'] * price
            st.write({'new_entry_plan': sizing})
        else:
            sizing = None
        if submit:
            try:
                if kind == 'BUY' and (sizing is None or quantity > sizing['quantity']):
                    raise ValueError('Entry exceeds permitted portfolio risk or exposure capacity')
                ledger.append(kind, symbol, quantity=int(quantity), price=price, stop=stop, fee=fee, note=note, event_id=st.session_state['edge_event_id'], expected_revision=revision)
                st.session_state['edge_event_id'] = str(uuid.uuid4())
                st.rerun()
            except ValueError as exc:
                st.error(str(exc))
        if events:
            history = pd.DataFrame(events)
            st.dataframe(numbered(history), use_container_width=True)
            export_section('Private trade journal', history, 'private_trade_journal')
    except Exception:
        st.error('Private ledger unavailable. No write success is assumed; retry after checking EDGE D1 configuration.')


def verify_d1():
    from edge_core.d1_store import d1_query
    owner = 'EDGE_TECHNICAL_PROBE_' + str(uuid.uuid4())
    ledger = Ledger(owner, d1_query)
    ledger.initialize()
    event_id = ledger.append('NOTE', 'TECHNICAL_PROBE', note='Synthetic storage verification; not a trade or market record')
    fresh = Ledger(owner, d1_query).events()
    if len(fresh) != 1 or fresh[0]['event_id'] != event_id or Ledger(owner + '_OTHER', d1_query).events():
        raise RuntimeError('D1 persistence or owner-isolation verification failed')
    published = d1_query('SELECT run_id, rows_count FROM edge_snapshot_runs ORDER BY generated_utc DESC LIMIT 1')
    if not published:
        raise RuntimeError('No published EDGE D1 research snapshot')
    count = d1_query('SELECT COUNT(*) AS n FROM edge_leadership WHERE run_id=?', (published[0]['run_id'],))
    if not count or int(count[0]['n']) != int(published[0]['rows_count']):
        raise RuntimeError('Published D1 research row count mismatch')
    print(json.dumps({'ledger_write_read_verified': True, 'owner_isolation_verified': True,
                      'synthetic_probe_event': event_id, 'research_run': published[0]['run_id'], 'research_rows': count[0]['n']}))


if __name__ == '__main__':
    import sys
    if sys.argv[1:] != ['verify-d1']:
        raise SystemExit('Usage: python -m edge_workspace verify-d1')
    verify_d1()
