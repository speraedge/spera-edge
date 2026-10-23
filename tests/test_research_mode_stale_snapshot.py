"""Regression guards: stale market snapshots remain research-visible, execution locked."""
import ast
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class ResearchModeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = (ROOT / "app.py").read_text()
        cls.workspace = (ROOT / "edge_workspace.py").read_text()

    def test_research_tables_not_gated_by_freshness(self):
        self.assertIn('render_entries(close,high,low,volume,edge_meta["last_session"])', self.app)
        self.assertNotIn('if snapshot_usable:\n                    render_entries(', self.app)
        self.assertIn('render_market(prices)', self.app)

    def test_informational_last_session_banner(self):
        self.assertIn('st.info(f"Note: Displaying research data from {last_session.isoformat()}. Execution forms are locked until fresh price data is available.")', self.app)
        self.assertNotIn('st.error(f"Snapshot does not match', self.app)

    def test_private_journal_is_disabled_and_guarded_server_side(self):
        self.assertIn("st.form_submit_button('Record private event', disabled=not snapshot_usable)", self.workspace)
        self.assertIn("if not snapshot_usable:\n                    raise ValueError('Execution locked: stale snapshot')", self.workspace)

    def test_position_sizing_controls_disabled(self):
        for field in ('Account equity (INR)', 'Permitted risk per trade (%)',
                      'Portfolio risk ceiling (%)', 'Gross exposure limit (%)',
                      'Single position limit (%)'):
            matching = [line for line in self.workspace.splitlines() if 'st.number_input(' in line and field in line]
            self.assertEqual(len(matching), 1, field)
            self.assertIn('disabled=not snapshot_usable', matching[0])

    def test_no_calendar_year_or_holiday_estimates(self):
        self.assertNotIn('2027', self.app)
        ast.parse(self.app)
        ast.parse(self.workspace)


if __name__ == '__main__':
    unittest.main()
