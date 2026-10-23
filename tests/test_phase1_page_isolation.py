"""Phase 1 page isolation and exports preflight (AST, no live Streamlit claims)."""
import ast
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PAGES = ["Market Pulse", "Leadership Scanner", "Trade Desk", "Portfolio & Journal", "Financial Evidence Review"]


class Phase1PageIsolation(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tree = ast.parse((ROOT / "app.py").read_text(encoding="utf-8"))

    def test_five_conditional_pages(self):
        found = []
        for node in self.tree.body:
            if not isinstance(node, ast.If):
                continue
            current = node
            while isinstance(current, ast.If):
                test = current.test
                if (isinstance(test, ast.Compare) and isinstance(test.left, ast.Name)
                    and test.left.id == "page" and len(test.comparators) == 1
                    and isinstance(test.comparators[0], ast.Constant)):
                    found.append(test.comparators[0].value)
                current = current.orelse[0] if len(current.orelse) == 1 else None
        self.assertEqual(found, PAGES)

    def test_no_eager_snapshot_loading_on_other_pages(self):
        source = (ROOT / "app.py").read_text(encoding="utf-8")
        self.assertIn('page in ("Market Pulse", "Portfolio & Journal")', source)
        self.assertIn('render_private_portfolio(prices,snapshot_usable)', source)

    def test_export_calls_preserved_in_pages(self):
        page_root = next(n for n in self.tree.body if isinstance(n, ast.If)
                         and isinstance(n.test, ast.Compare)
                         and isinstance(n.test.left, ast.Name) and n.test.left.id == "page")
        calls = [n for n in ast.walk(page_root) if isinstance(n, ast.Call)
                 and isinstance(n.func, ast.Name) and n.func.id == "export_section"]
        self.assertGreaterEqual(len(calls), 5)

    def test_frozen_modules_not_shadowed(self):
        source = (ROOT / "app.py").read_text(encoding="utf-8")
        self.assertNotIn("st.tabs(", source)
        self.assertIn("from edge_core.momentum_v1 import apply_frozen_v1_scores", source)
        self.assertIn("from edge_core.setup_scanner import compute_setup_scanner", source)


if __name__ == "__main__":
    unittest.main()
