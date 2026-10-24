import csv
import io
import unittest
import zipfile
from tools.build_bse_bhavcopy_mapping import parse_bhavcopy, match

class BhavcopyMappingTests(unittest.TestCase):
    def test_zip_isin_join_and_ambiguity(self):
        content = b"SC_CODE,ISIN_CODE\n500325,INE002A01018\n500326,INE002A01018\n532540,INE040A01034\n"
        archive = io.BytesIO()
        with zipfile.ZipFile(archive, "w") as z:
            z.writestr("EQ_ISINCODE.csv", content)
        pairs = parse_bhavcopy(archive.getvalue())
        self.assertEqual(match([("RELIANCE", "INE002A01018"), ("TCS", "INE040A01034")], pairs),
                         [{"Symbol": "TCS", "ISIN": "INE040A01034", "bse_scripcode": "532540"}])

    def test_reject_unexpected_columns(self):
        with self.assertRaises(ValueError):
            parse_bhavcopy(b"Symbol,ISIN\nABC,INE002A01018\n")

if __name__ == "__main__":
    unittest.main()
