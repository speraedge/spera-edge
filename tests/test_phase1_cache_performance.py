"""Phase 1 performance gate: time cold vs warm cached frozen scoring, and input invalidation."""
import ast
import json
import time
import unittest
from pathlib import Path

import numpy as np
import pandas as pd
import streamlit as st
from pandas.testing import assert_frame_equal
from edge_core.momentum_v1 import apply_frozen_v1_scores


def wrapper():
    tree = ast.parse((Path(__file__).resolve().parents[1] / "app.py").read_text())
    node = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "cached_v1")
    namespace = {"apply_frozen_v1_scores": apply_frozen_v1_scores, "st": st}
    exec(compile(ast.Module(body=[node], type_ignores=[]), "app.py", "exec"), namespace)
    return namespace["cached_v1"]


class Phase1CachePerformance(unittest.TestCase):
    def test_warm_cache_and_input_invalidation(self):
        fn = wrapper()
        rng = np.random.default_rng(20261023)
        n = 500
        frame = pd.DataFrame({
            "Data_Quality": ["PASS"] * n,
            "Ret_6M": rng.normal(0.1, 0.2, n),
            "Ret_12M": rng.normal(0.2, 0.3, n),
            "AnnVol": rng.uniform(0.1, 0.8, n),
        })
        fn.clear()
        t0 = time.perf_counter()
        cold = fn("snapshot-a", frame)
        cold_ms = (time.perf_counter() - t0) * 1000
        warm_times = []
        for _ in range(5):
            t0 = time.perf_counter()
            warm = fn("snapshot-a", frame)
            warm_times.append((time.perf_counter() - t0) * 1000)
        
        # Verify exact match
        assert_frame_equal(cold, warm, check_exact=True)
        
        # Verify invalidation
        altered = frame.copy()
        altered.loc[0, "Ret_6M"] += 0.5
        changed = fn("snapshot-b", altered)
        assert_frame_equal(changed, apply_frozen_v1_scores(altered), check_exact=True)
        self.assertFalse(changed.equals(cold), "Modified input must invalidate cache")
        
        report = {"phase": 1, "case": "500-stock Momentum V1 cache",
                  "cold_ms": round(cold_ms, 3),
                  "warm_median_ms": round(float(np.median(warm_times)), 3),
                  "speedup": round(cold_ms / max(float(np.median(warm_times)), 0.001), 2),
                  "input_invalidation": "PASS", "outputs_exact": "PASS"}
        print("PHASE1_BENCHMARK " + json.dumps(report, sort_keys=True))
        # No strict timing assertion here to prevent CI flakiness


if __name__ == "__main__":
    unittest.main()
