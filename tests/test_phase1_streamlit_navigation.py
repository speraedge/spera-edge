"""Phase 1 Streamlit AppTest: exercise real widget navigation with no published snapshot.

This checks UI execution and the fail-closed empty-data state. It is not
a production snapshot or browser download certification.
"""
import unittest
from pathlib import Path

from streamlit.testing.v1 import AppTest


APP = str(Path(__file__).resolve().parents[1] / "app.py")
PAGES = ["Market Pulse", "Leadership Scanner", "Trade Desk",
         "Portfolio & Journal", "Financial Evidence Review"]


class Phase1StreamlitNavigation(unittest.TestCase):
    def test_all_pages_render_without_uncaught_exception(self):
        at = AppTest.from_file(APP, default_timeout=45).run()
        self.assertEqual(len(at.exception), 0, [x.message for x in at.exception])
        self.assertGreaterEqual(len(at.sidebar.radio), 1)
        radio = at.sidebar.radio[0]
        self.assertEqual(list(radio.options), PAGES)
        for page in PAGES:
            with self.subTest(page=page):
                at.sidebar.radio[0].set_value(page).run()
                self.assertEqual(len(at.exception), 0,
                                 [x.message for x in at.exception])
                self.assertEqual(at.sidebar.radio[0].value, page)


if __name__ == "__main__":
    unittest.main()
