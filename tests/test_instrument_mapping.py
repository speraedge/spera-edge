import unittest
import json
import pandas as pd
from edge_core.instrument_mapping import parse_instrument_master,join_official_universe

class InstrumentMappingTests(unittest.TestCase):
    def test_isin_join(self):
        master=parse_instrument_master(json.dumps([
            {"segment":"NSE_EQ","isin":"INE002A01018","instrument_key":"NSE_EQ|INE002A01018","trading_symbol":"RELIANCE"},
            {"segment":"NSE_FO","isin":"INE002A01018","instrument_key":"NSE_FO|x","trading_symbol":"RELIANCE"}
        ]))
        official=pd.DataFrame({"Symbol":["RELIANCE","MISSING"],"ISIN Code":["INE002A01018","INE000000001"]})
        mapped=join_official_universe(official,master)
        self.assertEqual(mapped["Mapping_Status"].tolist(),["MAPPED","MISSING"])
    def test_ambiguous_isin_quarantined(self):
        row={"segment":"NSE_EQ","isin":"INE002A01018","instrument_key":"NSE_EQ|X","trading_symbol":"A"}
        other=dict(row,instrument_key="NSE_EQ|Y")
        with self.assertRaises(ValueError):
            parse_instrument_master(json.dumps([row,other]))
    def test_duplicate_official_isin_rejected(self):
        master=parse_instrument_master(json.dumps([{"segment":"NSE_EQ","isin":"A","instrument_key":"NSE_EQ|A","trading_symbol":"A"}]))
        official=pd.DataFrame({"Symbol":["A","B"],"ISIN Code":["A","A"]})
        with self.assertRaises(ValueError):
            join_official_universe(official,master)

if __name__=="__main__":
    unittest.main()
