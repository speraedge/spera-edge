import csv
from io import StringIO, BytesIO
import sqlite3
import unittest
from openpyxl import load_workbook
import pandas as pd
from edge_workspace import Ledger
from edge_exports import export_bytes


class CompletionSecurityTests(unittest.TestCase):
    def setUp(self):
        self.database = sqlite3.connect(':memory:')
        self.database.row_factory = sqlite3.Row
        self.addCleanup(self.database.close)
        self.ledger = Ledger('synthetic-owner', self.query)
        self.ledger.initialize()

    def query(self, sql, params=()):
        return [dict(row) for row in self.database.execute(sql, params).fetchall()]

    def test_private_trade_decision_and_link_tables_are_append_only(self):
        self.ledger.append('BUY', 'SYNTHETIC', quantity=2, price=100, stop=90, event_id='buy')
        self.query('INSERT INTO edge_setup_decisions VALUES (?,?,?,?)', ('synthetic-owner', 'decision', '2026-01-01', '{"decision":"TAKE","symbol":"SYNTHETIC"}'))
        self.query('INSERT INTO edge_decision_trade_links VALUES (?,?,?,?)', ('synthetic-owner', 'decision', 'buy', '2026-01-01'))
        for table in ('edge_trade_events', 'edge_setup_decisions', 'edge_decision_trade_links'):
            for sql in (f'DELETE FROM {table} WHERE owner_id=?', f'UPDATE {table} SET created_utc=? WHERE owner_id=?'):
                params = ('synthetic-owner',) if sql.startswith('DELETE') else ('changed', 'synthetic-owner')
                with self.subTest(table=table, statement=sql), self.assertRaises(sqlite3.IntegrityError):
                    self.query(sql, params)
        self.assertEqual(len(self.ledger.events()), 1)

    def test_database_rejects_cross_owner_and_symbol_only_links(self):
        self.ledger.append('BUY', 'SYNTHETIC', quantity=1, price=100, stop=90, event_id='buy')
        self.query('INSERT INTO edge_setup_decisions VALUES (?,?,?,?)', ('other-owner', 'foreign-decision', '2026-01-01', '{"decision":"TAKE","symbol":"SYNTHETIC"}'))
        with self.assertRaises(sqlite3.IntegrityError):
            self.query('INSERT INTO edge_decision_trade_links VALUES (?,?,?,?)', ('synthetic-owner', 'foreign-decision', 'buy', '2026-01-01'))

    def test_revision_gap_is_not_silently_treated_as_valid_history(self):
        self.ledger.append('NOTE', 'SYNTHETIC', event_id='first')
        self.query('INSERT INTO edge_trade_events SELECT owner_id,?,3,created_utc,payload FROM edge_trade_events', ('gap',))
        with self.assertRaisesRegex(ValueError, 'revision'):
            self.ledger.events()

    def test_non_trade_fees_cannot_disappear_from_performance(self):
        with self.assertRaises(ValueError):
            self.ledger.append('NOTE', 'SYNTHETIC', fee=5)

    def test_exported_private_text_cannot_become_spreadsheet_formulas(self):
        original = pd.DataFrame({'Note': ['=1+1', '  @SUM(1,1)', '+1+1', '-1+1'], 'PnL': [-12.5] * 4})
        csv_rows = list(csv.DictReader(StringIO(export_bytes(original, 'CSV', 'Private').decode('utf-8-sig'))))
        self.assertTrue(all(row['Note'].startswith("'") for row in csv_rows))
        workbook = load_workbook(BytesIO(export_bytes(original, 'Excel', 'Private')), data_only=False)
        self.assertTrue(all(workbook.active.cell(row, 2).data_type != 'f' for row in range(2, 6)))
        self.assertEqual(workbook.active.cell(2, 3).value, -12.5)
        self.assertEqual(original.iloc[0]['Note'], '=1+1')

    def test_live_probe_namespace_cannot_read_canonical_private_records(self):
        from edge_core.private_integrity import synthetic_private_query
        self.ledger.append('NOTE', 'SYNTHETIC', note='Canonical test record')
        isolated = Ledger('synthetic-owner', synthetic_private_query(self.query, 'edge_audit_' + 'a' * 32 + '_'))
        isolated.initialize()
        self.assertEqual(isolated.events(), [])
        isolated.append('NOTE', 'SYNTHETIC', note='Isolated probe record')
        self.assertEqual(self.ledger.events()[0]['note'], 'Canonical test record')

    def test_pdf_review_notes_are_not_silently_truncated(self):
        from unittest.mock import patch
        from reportlab.platypus import Table
        source = pd.DataFrame({'Note': ['long review note ' * 50 + 'END_PRIVATE_NOTE']})
        with patch('reportlab.platypus.Table', wraps=Table) as tables:
            self.assertTrue(export_bytes(source, 'PDF', 'Private review').startswith(b'%PDF'))
        cells = [cell for call in tables.call_args_list for row in call.args[0] for cell in row]
        text = ' '.join(cell.getPlainText() if hasattr(cell, 'getPlainText') else str(cell) for cell in cells)
        self.assertIn('END_PRIVATE_NOTE', text)

    def test_only_selected_export_format_is_generated(self):
        from unittest.mock import MagicMock, patch
        from edge_exports import export_section
        with patch('edge_exports.st') as ui, patch('edge_exports.export_bytes', return_value=b'csv') as exporter:
            ui.selectbox.return_value = 'CSV'
            ui.columns.return_value = [MagicMock(), MagicMock(), MagicMock()]
            export_section('Synthetic', pd.DataFrame({'Value': [1]}), 'synthetic')
        self.assertEqual(exporter.call_count, 1)
        self.assertEqual(exporter.call_args.args[1], 'CSV')

    def test_legacy_membership_blocks_readiness_with_clear_warning(self):
        from unittest.mock import patch
        from edge_trader_readiness_ui import render_trader_readiness
        with patch('edge_trader_readiness_ui.st') as ui:
            leadership = pd.DataFrame({'Symbol': ['SYNTHETIC'], 'Data_Quality': ['REVIEW'],
                                       'Ret_6M': [.2], 'Ret_12M': [.4], 'AnnVol': [.2]})
            render_trader_readiness(leadership, pd.DataFrame({'Symbol': ['SYNTHETIC']}),
                                   pd.DataFrame(), '2026-09-30', snapshot_fresh=True)
        self.assertTrue(ui.warning.called)
        self.assertFalse(ui.error.called)

    def test_research_to_manual_trade_and_review_never_infers_a_fill(self):
        import json
        from edge_workspace import market_report, entry_diagnostics, plan_quantity
        from edge_core.momentum_v1 import apply_frozen_v1_scores
        from edge_core.leadership_levels import classify_leadership
        from edge_core.setup_decisions import validate_decision
        from edge_core.decision_outcomes import decision_outcomes
        from edge_core.decision_links import validate_trade_link
        from edge_core.trade_review import journal_quality
        dates = pd.bdate_range('2025-01-01', periods=260)
        close = pd.DataFrame({'SYNTHETIC': range(100, 360)}, index=dates, dtype=float)
        self.assertEqual(market_report(close)['latest_coverage'], 1)
        ranks = apply_frozen_v1_scores(pd.DataFrame({'Symbol': ['SYNTHETIC'],
            'Data_Quality': ['REVIEW'], 'Ret_6M': [.2], 'Ret_12M': [.4], 'AnnVol': [.2]}))
        self.assertFalse(classify_leadership(ranks, close)['SEPA_Certified'].any())
        entries = entry_diagnostics(close, close + 1, close - 1, close * 0 + 1000, dates[-1])
        self.assertFalse(entries['SEPA_Certified'].any())
        self.assertGreater(plan_quantity(100000, 1, 100, 90, 0, 0)['quantity'], 0)
        payload = validate_decision('SYNTHETIC', str(dates[250].date()), 'TAKE', 'OTHER', 'Synthetic workflow test')
        self.query('INSERT INTO edge_setup_decisions VALUES (?,?,?,?)',
                   ('synthetic-owner', 'decision', 'synthetic-created-time', json.dumps(payload)))
        decisions = [dict(payload, decision_id='decision')]
        observation = decision_outcomes(decisions, close, 2).iloc[0]
        self.assertEqual(observation['Observation'], 'OBSERVED')
        self.assertEqual(self.ledger.events(), [])
        self.assertTrue(self.ledger.report({})[0].empty)
        self.ledger.append('BUY', 'SYNTHETIC', quantity=10, price=100, stop=90, note='Explicit test fill', event_id='buy')
        validate_trade_link(decisions, self.ledger.events(), 'decision', 'buy')
        self.query('INSERT INTO edge_decision_trade_links VALUES (?,?,?,?)',
                   ('synthetic-owner', 'decision', 'buy', 'synthetic-created-time'))
        self.ledger.append('SELL', 'SYNTHETIC', quantity=4, price=110, fee=2)
        positions, actual = self.ledger.report({'SYNTHETIC': 105})
        self.assertEqual(positions.iloc[0]['Quantity'], 6)
        self.assertEqual(actual['realized'], 38)
        self.assertEqual(actual['unrealized'], 30)
        self.assertEqual(journal_quality(self.ledger.events()).iloc[0]['Review_Status'], 'DOCUMENTED_BUYS')

    def test_two_competing_exits_cannot_oversell(self):
        from concurrent.futures import ThreadPoolExecutor
        from pathlib import Path
        from tempfile import TemporaryDirectory
        from threading import Barrier
        with TemporaryDirectory() as directory:
            path = Path(directory) / 'synthetic.db'
            barrier = Barrier(2)
            def query(sql, params=()):
                if sql.lstrip().startswith('INSERT INTO edge_trade_events') and params[2] == 2:
                    barrier.wait(timeout=5)
                connection = sqlite3.connect(path, timeout=5, isolation_level=None)
                connection.row_factory = sqlite3.Row
                try:
                    return [dict(row) for row in connection.execute(sql, params).fetchall()]
                finally:
                    connection.close()
            ledger = Ledger('synthetic-owner', query)
            ledger.initialize()
            ledger.append('BUY', 'SYNTHETIC', quantity=10, price=100, stop=90)
            def exit_position(_):
                try:
                    ledger.append('SELL', 'SYNTHETIC', quantity=7, price=110, expected_revision=1)
                    return 'ACCEPTED'
                except ValueError:
                    return 'REJECTED'
            with ThreadPoolExecutor(max_workers=2) as pool:
                outcomes = list(pool.map(exit_position, range(2)))
            self.assertCountEqual(outcomes, ['ACCEPTED', 'REJECTED'])
            self.assertEqual(ledger.report({'SYNTHETIC': 110})[0].iloc[0]['Quantity'], 3)
