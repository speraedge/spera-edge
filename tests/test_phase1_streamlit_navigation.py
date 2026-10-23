"""Phase 1: Streamlit AppTest with isolated, intentionally empty snapshot."""
import unittest
from pathlib import Path
from unittest.mock import patch
from streamlit.testing.v1 import AppTest

APP = str(Path(__file__).resolve().parents[1] / "app.py")
PAGES = ["Market Pulse", "Leadership Scanner", "Trade Desk",
         "Portfolio & Journal", "Financial Evidence Review"]


class Phase1StreamlitNavigation(unittest.TestCase):
    def test_all_pages_render_without_uncaught_exception(self):
        original = Path.is_file

        def no_snapshot(path):
            if "/data/latest/" in str(path).replace(chr(92), "/"):
                return False
            return original(path)

        # AppTest must not load a real 500-stock snapshot in the CI smoke test.
        # This tests fail-closed navigation, not full-data render performance.
        with patch.object(Path, "is_file", no_snapshot):
            at = AppTest.from_file(APP, default_timeout=20).run()
            self.assertEqual(len(at.exception), 0, [x.message for x in at.exception])
            self.assertGreaterEqual(len(at.sidebar.radio), 1)
            self.assertEqual(list(at.sidebar.radio[0].options), PAGES)
            for page in PAGES:
                with self.subTest(page=page):
                    at.sidebar.radio[0].set_value(page).run()
                    self.assertEqual(len(at.exception), 0,
                                     [x.message for x in at.exception])
                    self.assertEqual(at.sidebar.radio[0].value, page)


if __name__ == "__main__":
    unittest.main()
