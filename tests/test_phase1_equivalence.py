"""Phase 1 regression: verify cached wrappers preserve frozen research outputs.

Run: python -m unittest tests.test_phase1_equivalence -v
No provider/network access and no frozen source modifications.
"""
import ast
import unittest
from pathlib import Path
from unittest.mock import Mock
import numpy as np
import pandas as pd
from pandas.testing import assert_frame_equal

from edge_core.momentum_v1 import apply_frozen_v1_scores
from edge_core.setup_scanner import compute_setup_scanner
from edge_core.breakout_health import breakout_health
from edge_core.analytics import stage2_template


class Phase1Equivalence(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        tree = ast.parse((Path(__file__).resolve().parents[1] / "app.py").read_text())
        names = {"cached_v1", "cached_setups", "cached_breakout_health", "cached_stage2_diagnostics"}
        functions = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name in names]
        assert {f.name for f in functions} == names
        for f in functions:
            f.decorator_list = []
        namespace = dict(pd=pd, apply_frozen_v1_scores=apply_frozen_v1_scores,
                         compute_setup_scanner=compute_setup_scanner,
                         breakout_health=breakout_health, stage2_template=stage2_template)
        exec(compile(ast.Module(body=functions, type_ignores=[]), "app.py", "exec"), namespace)
        cls.w = namespace

    def test_frozen_scoring_exact(self):
        frame = pd.DataFrame({
            "Data_Quality": ["PASS", "REVIEW", "PASS", "FAIL", "PASS"],
            "Ret_6M": [0.2, 0.1, -0.05, 0.3, 0.4],
            "Ret_12M": [0.3, 0.15, -0.1, 0.4, 0.5],
            "AnnVol": [0.25, 0.2, 0.3, 0.2, 0.35],
        }, index=["AAA", "BBB", "CCC", "DDD", "EEE"])
        before = frame.copy(deep=True)
        assert_frame_equal(self.w["cached_v1"]("snapshot-test", frame), apply_frozen_v1_scores(frame), check_exact=True)
        assert_frame_equal(frame, before, check_exact=True)

    def test_stage2_exact(self):
        idx = pd.bdate_range("2025-01-01", periods=260)
        close = pd.DataFrame({"AAA": np.linspace(100, 220, 260),
                              "BBB": np.linspace(220, 100, 260)}, index=idx)
        actual = self.w["cached_stage2_diagnostics"]("snapshot-test", close)
        expected = pd.DataFrame([
            {"Symbol": sym, "Price-template pass": stage2_template(close[sym])["eligible"],
             "Note": stage2_template(close[sym])["reason"]} for sym in close
        ])
        assert_frame_equal(actual, expected, check_exact=True)

    def test_setup_scanner_exact(self):
        idx = pd.bdate_range("2025-01-01", periods=260)
        close = pd.DataFrame({"AAA": np.linspace(100, 200, 260),
                              "BBB": np.linspace(120, 140, 260)}, index=idx)
        high, low = close * 1.01, close * 0.99
        volume = pd.DataFrame(100000.0, index=idx, columns=close.columns)
        actual = self.w["cached_setups"]("snapshot-test", close, volume, high, low)
        expected = compute_setup_scanner(close, volume, high_df=high, low_df=low)
        assert_frame_equal(actual, expected, check_exact=True)
        actual_subset = self.w["cached_setups"]("snapshot-test", close, volume, high, low, symbols=("AAA",))
        expected_subset = compute_setup_scanner(close, volume, symbols=["AAA"], high_df=high, low_df=low)
        assert_frame_equal(actual_subset, expected_subset, check_exact=True)

    def test_breakout_health_exact(self):
        idx = pd.bdate_range("2025-01-01", periods=260)
        close = pd.DataFrame({"AAA": np.linspace(100, 200, 260)}, index=idx)
        high, low = close * 1.01, close * 0.99
        volume = pd.DataFrame(100000.0, index=idx, columns=close.columns)
        actual = self.w["cached_breakout_health"]("snapshot-test", close, high, volume, low)
        expected = breakout_health(close, high, volume, low=low)
        self.assertEqual(actual.keys(), expected.keys())
        for key in actual:
            if isinstance(actual[key], pd.DataFrame):
                assert_frame_equal(actual[key], expected[key], check_exact=True)
            else:
                self.assertEqual(actual[key], expected[key])


if __name__ == "__main__":
    unittest.main()
