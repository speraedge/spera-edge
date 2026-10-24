"""Training export contracts: actual CSV and XLSX bytes, not only button presence."""
from io import BytesIO
from pathlib import Path
import unittest
import pandas as pd
from openpyxl import load_workbook
from edge_exports import export_bytes


ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / "app.py").read_text()
WORKSPACE = (ROOT / "edge_workspace.py").read_text()


class TrainingExports(unittest.TestCase):
    def test_eight_training_exports_wired(self):
        contracts = [
            (WORKSPACE, "market_breadth_history"),
            (APP, "edge_breakout_outcomes"),
            (APP, "vcp_candidates"),
            (WORKSPACE, "entry_diagnostics"),
            (APP, "private_saved_trade_plans"),
            (WORKSPACE, "private_positions"),
            (WORKSPACE, "private_equity_curve"),
            (WORKSPACE, "private_closed_lot_r"),
        ]
        for source, key in contracts:
            with self.subTest(key=key):
                self.assertIn('"' + key + '"', source) if key.startswith("edge_") else self.assertTrue(
                    ('"' + key + '"') in source or ("'" + key + "'") in source)

    def test_csv_and_excel_bytes_for_each_export_shape(self):
        shapes = {
            "market_breadth_history": {"Date": ["2026-10-22"], "Above_50_Pct": [55.0]},
            "edge_breakout_outcomes": {"Symbol": ["AAA"], "Outcome": ["SUCCESS"]},
            "vcp_candidates": {"Symbol": ["AAA"], "Pivot": [102.5]},
            "entry_diagnostics": {"Symbol": ["AAA"], "Stop": [95.0]},
            "private_saved_trade_plans": {"Symbol": ["AAA"], "Setup Date": ["2026-10-22"], "Status": ["WAITING"]},
            "private_positions": {"Symbol": ["AAA"], "Quantity": [10]},
            "private_equity_curve": {"Date": ["2026-10-22"], "Equity": [510000.0]},
            "private_closed_lot_r": {"Sell_Event_ID": ["e1"], "R_Multiple": [2.0]},
        }
        for name, columns in shapes.items():
            with self.subTest(name=name):
                frame = pd.DataFrame(columns)
                csv = export_bytes(frame, "CSV", name)
                self.assertTrue(csv.startswith(bytes((0xEF, 0xBB, 0xBF))))
                parsed = pd.read_csv(BytesIO(csv))
                self.assertEqual(len(parsed), 1)
                self.assertEqual(parsed.loc[0, "No."], 1)
                xlsx = export_bytes(frame, "Excel", name)
                book = load_workbook(BytesIO(xlsx), read_only=True, data_only=True)
                sheet = book.active
                self.assertEqual(sheet.max_row, 2)
                self.assertEqual(sheet.cell(1, 1).value, "No.")
                book.close()

    def test_private_saved_plan_export_stays_inside_owner_guard(self):
        start = APP.index('    if plan_store is not None:')
        end = APP.index('    trade_ranks,', start)
        self.assertIn('export_section("Private saved trade plans"', APP[start:end])
        self.assertNotIn('export_section("Private saved trade plans"', APP[:start])


if __name__ == "__main__":
    unittest.main()
