import unittest
import pandas as pd
from edge_core.journal_analytics import (
    equity_curve, max_drawdown, r_multiples, expectancy, INSUFFICIENT_HISTORY)


def event(kind, revision, qty=0, price=0, stop=0, fee=0, day='2026-10-20', symbol='ABC'):
    return dict(kind=kind, symbol=symbol, quantity=qty, price=price, stop=stop,
                fee=fee, revision=revision, event_id=str(revision),
                created_utc=day + 'T10:00:00+00:00')


class Phase5JournalAnalytics(unittest.TestCase):
    def test_equity_from_observed_marks_and_cash(self):
        events = [event('BUY', 1, 2, 100, 95, 2)]
        marks = pd.DataFrame({'ABC': [110., 90.]},
                             index=pd.to_datetime(['2026-10-20', '2026-10-21']))
        curve, status = equity_curve(events, marks, initial_cash=1000)
        self.assertEqual(status, 'OK')
        self.assertEqual(curve['Equity'].tolist(), [1018., 978.])
        dd = max_drawdown(curve)
        self.assertEqual(dd['status'], 'OK')
        self.assertAlmostEqual(dd['max_drawdown_pct'], 100 * 40 / 1018)

    def test_missing_mark_or_capital_fails_closed(self):
        events = [event('BUY', 1, 1, 100, 95)]
        marks = pd.DataFrame({'ABC': [float('nan')]},
                             index=pd.to_datetime(['2026-10-20']))
        for capital in (None, 0, 1000):
            _, status = equity_curve(events, marks, initial_cash=capital)
            self.assertEqual(status, INSUFFICIENT_HISTORY)
        self.assertEqual(max_drawdown(pd.DataFrame())['status'], INSUFFICIENT_HISTORY)

    def test_original_r_ignores_updated_stop_and_includes_fees(self):
        events = [event('BUY', 1, 10, 100, 95, 10),
                  event('STOP', 2, stop=110),
                  event('SELL', 3, 4, 112, fee=4)]
        trades, status = r_multiples(events)
        self.assertEqual(status, 'OK')
        self.assertAlmostEqual(trades.iloc[0]['Original_Risk'], 20)
        self.assertAlmostEqual(trades.iloc[0]['Realized_PnL'], 40)
        self.assertAlmostEqual(trades.iloc[0]['R_Multiple'], 2)
        self.assertAlmostEqual(expectancy(trades)['expectancy_r'], 2)

    def test_fifo_partial_exits_and_no_inferred_fills(self):
        events = [event('BUY', 1, 2, 100, 95), event('BUY', 2, 2, 110, 105),
                  event('SELL', 3, 3, 120)]
        trades, status = r_multiples(events)
        self.assertEqual(status, 'OK')
        self.assertEqual(trades['Quantity'].tolist(), [2, 1])
        self.assertAlmostEqual(trades['R_Multiple'].iloc[0], 4)
        self.assertAlmostEqual(trades['R_Multiple'].iloc[1], 2)
        self.assertEqual(expectancy(trades)['closed_lots'], 2)
        self.assertEqual(r_multiples([event('BUY', 1, 1, 100, 95)])[1],
                         INSUFFICIENT_HISTORY)

    def test_event_after_last_mark_not_silently_ignored(self):
        events = [event('BUY', 1, 1, 100, 95, day='2026-10-22')]
        marks = pd.DataFrame({'ABC': [100.]},
                             index=pd.to_datetime(['2026-10-20']))
        self.assertEqual(equity_curve(events, marks, initial_cash=1000)[1],
                         INSUFFICIENT_HISTORY)

    def test_no_research_or_owner_data_in_public_outputs(self):
        import inspect
        import edge_core.journal_analytics as analytics
        source = inspect.getsource(analytics)
        self.assertNotIn('data/latest/', source)
        self.assertNotIn('st.session_state', source)


if __name__ == '__main__':
    unittest.main()
