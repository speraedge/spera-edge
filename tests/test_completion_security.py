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
