"""Phase 1: verify CSV/Excel/PDF export payloads without browser download claims."""
import io
import unittest

import pandas as pd
from openpyxl import load_workbook

from edge_exports import export_bytes


class Phase1ExportPayloads(unittest.TestCase):
    def setUp(self):
        self.frame = pd.DataFrame({
            "Symbol": ["AAA", "BBB"],
            "Momentum": [1.5, 2.25],
            "Notes": ["=HYPERLINK(\"x\")", "Normal"],
        })

    def test_csv_roundtrip(self):
        raw = export_bytes(self.frame, "CSV", "Research")
        restored = pd.read_csv(io.BytesIO(raw), encoding="utf-8-sig")
        self.assertEqual(restored["Symbol"].tolist(), ["AAA", "BBB"])
        self.assertEqual(restored["No."].tolist(), [1, 2])
        self.assertTrue(restored.loc[0, "Notes"].startswith("'="))

    def test_excel_roundtrip(self):
        raw = export_bytes(self.frame, "Excel", "Research")
        wb = load_workbook(io.BytesIO(raw), read_only=True, data_only=False)
        ws = wb.active
        self.assertEqual(ws.max_row, 3)
        self.assertEqual(ws.cell(2, 2).value, "AAA")
        self.assertEqual(ws.cell(3, 3).value, 2.25)
        self.assertTrue(ws.cell(2, 4).value.startswith("'="))
        wb.close()

    def test_pdf_payload(self):
        raw = export_bytes(self.frame, "PDF", "Research")
        self.assertTrue(raw.startswith(b"%PDF"))
        self.assertGreater(len(raw), 500)


if __name__ == "__main__":
    unittest.main()
