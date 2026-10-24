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

    def test_udiff_filters_non_equity_and_matches_isin(self):
        csv_bytes = (b"TradDt,Sgmt,Src,FinInstrmTp,FinInstrmId,ISIN,TckrSymb\\n"
                     b"2026-10-23,CM,BSE,STK,500325,INE002A01018,RELIANCE\\n"
                     b"2026-10-23,CM,BSE,ETF,999999,INE002A01018,RELIANCEETF\\n"
                     b"2026-10-23,CM,BSE,STK,532540,INE040A01034,TCS\\n")
        pairs = parse_bhavcopy(csv_bytes)
        self.assertEqual(match([("RELIANCE", "INE002A01018"), ("TCS", "INE040A01034")], pairs),
                         [{"Symbol": "RELIANCE", "ISIN": "INE002A01018", "bse_scripcode": "500325"},
                          {"Symbol": "TCS", "ISIN": "INE040A01034", "bse_scripcode": "532540"}])

    def test_reject_unexpected_columns(self):
        with self.assertRaises(ValueError):
            parse_bhavcopy(b"Symbol,ISIN\nABC,INE002A01018\n")

if __name__ == "__main__":
    unittest.main()
