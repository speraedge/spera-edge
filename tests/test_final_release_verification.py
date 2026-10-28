"""Release gates: sizing, action adjustment provenance and FIFO accounting."""
import unittest
import pandas as pd
from edge_workspace import plan_quantity
from edge_core.indian_risk_gates import atr_stop
from edge_core.journal_analytics import r_multiples
from edge_core.corporate_action_evidence import review_events
import csv, tempfile
from pathlib import Path

class FinalVerificationTests(unittest.TestCase):
    def setUp(self):
        self.close = pd.Series([100.] * 20)
        self.high = self.close + 1
        self.low = self.close - 1
        self.volume = pd.Series([600000.] * 20)
        self.entry = 100.
        self.stop = atr_stop(self.entry, self.high, self.low, self.close)

    def sizing(self, **overrides):
        kw = dict(target=112, atr_candles=(self.high,self.low,self.close),
                  liquidity_candles=(self.close,self.volume),
                  earnings_within_five_days=False)
        kw.update(overrides)
        return plan_quantity(500000, 1, self.entry, self.stop, 0, 0, **kw)

    def test_sizing_success_when_all_verified_evidence_present(self):
        result = self.sizing()
        self.assertGreater(result["quantity"], 0)
        self.assertLessEqual(result["planned_risk"], 5000)

    def test_sizing_rejects_missing_earnings_and_liquidity_and_atr(self):
        for field in ('earnings_within_five_days','liquidity_candles','atr_candles'):
            kw = {field:None}
            with self.subTest(field=field), self.assertRaises(ValueError):
                self.sizing(**kw)

    def test_sizing_rejects_incorrect_atr_stop_and_low_liquidity(self):
        with self.assertRaises(ValueError):
            plan_quantity(500000, 1, self.entry, self.stop + 1, 0, 0,
                          target=112, atr_candles=(self.high,self.low,self.close),
                          liquidity_candles=(self.close,self.volume),
                          earnings_within_five_days=False)
        with self.assertRaisesRegex(ValueError, 'ADTV_BELOW_5_CRORE'):
            self.sizing(liquidity_candles=(self.close,pd.Series([100.] * 20)))

    def test_journal_original_r_partial_exit_and_fees(self):
        events = [
            dict(kind='BUY',symbol='ABC',quantity=10,price=100.,stop=95.,fee=10.,revision=1,event_id='1',created_utc='2026-10-20T10:00:00+00:00'),
            dict(kind='STOP',symbol='ABC',quantity=0,price=0.,stop=110.,fee=0.,revision=2,event_id='2',created_utc='2026-10-20T10:01:00+00:00'),
            dict(kind='SELL',symbol='ABC',quantity=4,price=112.,stop=0.,fee=4.,revision=3,event_id='3',created_utc='2026-10-20T10:02:00+00:00')]
        rows, state = r_multiples(events)
        self.assertEqual(state,'OK')
        self.assertEqual(len(rows),1)
        self.assertAlmostEqual(rows.iloc[0]['Original_Risk'],20.)
        self.assertAlmostEqual(rows.iloc[0]['Realized_PnL'],40.)

    def test_corporate_actions_never_claim_adjusted_prices_ready(self):
        with tempfile.TemporaryDirectory() as tmp:
            source=Path(tmp)/'events.csv'
            with source.open('w',newline='') as f:
                writer=csv.DictWriter(f,fieldnames=['symbol','isin','purpose','ex_date','source_url'])
                writer.writeheader()
                writer.writerow(dict(symbol='ABC',isin='INE000A00001',purpose='Split 1:2',ex_date='2026-10-20',source_url='https://www.nseindia.com/example'))
            result=review_events(source,Path(tmp)/'audit',{'ABC':'INE000A00001'})
            self.assertFalse(result['adjusted_prices_ready'])
            self.assertEqual(result['approved_factors'],0)
if __name__ == '__main__':
    unittest.main()
