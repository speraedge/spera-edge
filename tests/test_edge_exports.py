import unittest
import pandas as pd
from edge_exports import numbered, export_bytes


class ExportTests(unittest.TestCase):
    def test_numbering_starts_at_one_without_changing_rank(self):
        source = pd.DataFrame({"Symbol": ["AAA", "BBB"], "Pure_Momentum_Rank": [1, 2]})
        result = numbered(source)
        self.assertEqual(list(result.index), [1, 2])
        self.assertEqual(list(source.index), [0, 1])
        self.assertEqual(result["Pure_Momentum_Rank"].tolist(), [1, 2])

    def test_csv_excel_pdf_exports(self):
        source = pd.DataFrame({"Symbol": ["AAA"], "Pure_Momentum_Rank": [1]})
        self.assertIn(b"No.,Symbol,Pure_Momentum_Rank", export_bytes(source, "CSV", "Test"))
        self.assertTrue(export_bytes(source, "Excel", "Test").startswith(b"PK"))
        self.assertTrue(export_bytes(source, "PDF", "Test").startswith(b"%PDF"))


if __name__ == "__main__":
    unittest.main()
