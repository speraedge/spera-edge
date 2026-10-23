import sqlite3
import unittest
import pandas as pd
from edge_workspace import entry_diagnostics, market_report, Ledger, plan_quantity, identity_owner, industry_participation


class WorkspaceTests(unittest.TestCase):
    def test_current_industry_requires_dated_unique_membership(self):
        close, _, _, _ = self.candles()
        members = pd.DataFrame({'Symbol': ['ABC'], 'Industry': ['TEST']})
        report = industry_participation(close, members)
        self.assertEqual(report.iloc[0]['Industry'], 'TEST')
        self.assertEqual(report.iloc[0]['Price_Coverage'], 1)
        with self.assertRaises(ValueError):
            industry_participation(close, pd.concat([members, members]))

    def candles(self):
        dates = pd.bdate_range('2025-01-01', periods=260)
        close = pd.DataFrame({'ABC': [100.0] * 259 + [110.0]}, index=dates)
        volume = close * 0 + 1000
        volume.iloc[-1] = 2000
        return close, close + 1, close - 1, volume

    def test_pivot_excludes_breakout_and_future_sessions(self):
        close, high, low, volume = self.candles()
        result = entry_diagnostics(close, high, low, volume, close.index[-1])
        self.assertEqual(result.iloc[0]['Pivot'], 101)
        self.assertTrue(result.iloc[0]['Price_Breakout'])
        self.assertEqual(result.iloc[0]['Volume_Ratio'], 2)
        self.assertFalse(result.iloc[0]['SEPA_Certified'])
        before = entry_diagnostics(close, high, low, volume, close.index[-2])
        self.assertFalse(before.iloc[0]['Price_Breakout'])
        volume.iloc[-1] = 1000
        self.assertFalse(entry_diagnostics(close, high, low, volume, close.index[-1]).iloc[0]['Volume_Confirmed'])

    def test_missing_latest_price_is_not_forward_filled(self):
        close, high, low, volume = self.candles()
        close.iloc[-1] = float('nan')
        self.assertEqual(entry_diagnostics(close, high, low, volume, close.index[-1]).iloc[0]['Evidence'], 'INCOMPLETE_OHLCV')
        self.assertEqual(market_report(close)['latest_coverage'], 0)

    def test_budget_caps_exposure_and_existing_heat(self):
        self.assertEqual(plan_quantity(100000, 1, 100, 95, 4900, 95000)['quantity'], 20)
        self.assertEqual(plan_quantity(100000, 1, 100, 95, 5000, 0)['quantity'], 0)
        with self.assertRaises(ValueError):
            plan_quantity(100000, 1, 100, 101, 0, 0)
        with self.assertRaisesRegex(ValueError, 'maximum initial stop distance'):
            plan_quantity(100000, 1, 100, 90, 0, 0)
        self.assertGreater(plan_quantity(100000, 1, 100, 92, 0, 0)['quantity'], 0)

    def test_identity_requires_verified_allowed_email_and_subject(self):
        identity = {'email': 'owner@example.com', 'email_verified': True, 'sub': '123', 'iss': 'https://issuer'}
        self.assertTrue(identity_owner(identity, ['owner@example.com']))
        for field in ('email_verified', 'sub', 'iss'):
            bad = dict(identity)
            bad.pop(field)
            with self.assertRaises(ValueError):
                identity_owner(bad, ['owner@example.com'])
        with self.assertRaises(ValueError):
            identity_owner(identity, ['other@example.com'])

    def test_ledger_persists_partial_exits_and_isolates_owners(self):
        connection = sqlite3.connect(':memory:')
        connection.row_factory = sqlite3.Row
        def query(sql, params=()):
            return [dict(row) for row in connection.execute(sql, params).fetchall()]
        ledger = Ledger('owner', query)
        ledger.initialize()
        ledger.append('BUY', 'ABC', quantity=10, price=100, stop=95, fee=10, note='entry')
        ledger.append('SELL', 'ABC', quantity=4, price=120, fee=4)
        ledger.append('STOP', 'ABC', stop=105)
        positions, summary = Ledger('owner', query).report({'ABC': 110})
        self.assertEqual(positions.iloc[0]['Quantity'], 6)
        self.assertAlmostEqual(summary['realized'], 72)
        self.assertAlmostEqual(summary['unrealized'], 54)
        self.assertAlmostEqual(summary['open_risk'], 30)
        self.assertEqual(Ledger('other', query).events(), [])
        with self.assertRaises(ValueError):
            ledger.append('SELL', 'ABC', quantity=7, price=120)
        with self.assertRaises(ValueError):
            ledger.append('BUY', 'ABC', quantity=1.5, price=120, stop=110)
        self.assertIsNone(ledger.report({})[1]['exposure'])

    def test_stale_revision_and_duplicate_submission_are_safe(self):
        connection = sqlite3.connect(':memory:')
        connection.row_factory = sqlite3.Row
        def query(sql, params=()):
            return [dict(row) for row in connection.execute(sql, params).fetchall()]
        ledger = Ledger('owner', query)
        ledger.initialize()
        ledger.append('BUY', 'ABC', quantity=1, price=100, stop=95, event_id='same', expected_revision=0)
        ledger.append('BUY', 'ABC', quantity=1, price=100, stop=95, event_id='same', expected_revision=0)
        self.assertEqual(len(ledger.events()), 1)
        with self.assertRaises(ValueError):
            ledger.append('SELL', 'ABC', quantity=1, price=110, expected_revision=0)

    def test_frozen_formula_file_matches_authorized_source_archive(self):
        import hashlib
        from pathlib import Path
        current = (Path(__file__).parents[1] / 'edge_core' / 'momentum_v1.py').read_bytes()
        self.assertEqual(hashlib.sha256(current.replace(b'\r\n', b'\n')).hexdigest(), '3c83e3f5af6647db8a7c0631524f0b76f45370912578b0a3f8437b986b51332a')
