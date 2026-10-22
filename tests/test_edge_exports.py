import unittest
import pandas as pd
from io import BytesIO
from openpyxl import load_workbook
from edge_exports import numbered, export_bytes


class ExportTests(unittest.TestCase):
    def test_numbering_starts_at_one_without_changing_rank(self):
        source = pd.DataFrame({"Symbol": ["AAA", "BBB"], "Pure_Momentum_Rank": [1, 2]})
        result = numbered(source)
        self.assertEqual(list(result.index), [1, 2])
        self.assertEqual(list(source.index), [0, 1])
        self.assertEqual(result["Pure_Momentum_Rank"].tolist(), [1, 2])

    def test_wide_export_preserves_all_fields(self):
        fields = {"Symbol": ["AAA"]}
        fields.update({f"Field_{i}": [f"value_{i}"] for i in range(1, 16)})
        source = pd.DataFrame(fields)
        workbook = load_workbook(BytesIO(export_bytes(source, "Excel", "Wide")))
        self.assertEqual(workbook.active.max_column, 17)
        pdf = export_bytes(source, "PDF", "Wide")
        self.assertTrue(pdf.startswith(b"%PDF"))
        self.assertGreater(len(pdf), 2000)

    def test_empty_and_null_values(self):
        source = pd.DataFrame({"Symbol": ["AAA", "BBB"], "Score": [None, 4.5]})
        self.assertTrue(export_bytes(source, "PDF", "Nulls").startswith(b"%PDF"))

    def test_csv_excel_pdf_exports(self):
        source = pd.DataFrame({"Symbol": ["AAA"], "Pure_Momentum_Rank": [1]})
        self.assertIn(b"No.,Symbol,Pure_Momentum_Rank", export_bytes(source, "CSV", "Test"))
        self.assertTrue(export_bytes(source, "Excel", "Test").startswith(b"PK"))
        self.assertTrue(export_bytes(source, "PDF", "Test").startswith(b"%PDF"))


if __name__ == "__main__":
    unittest.main()
