# Rule conflicts — review only (no runtime rule changes)

The legacy modules `edge_core/risk_engine.py` and `edge_core/minervini_rules.py` are not directly imported by `app.py` or `edge_workspace.py` (inspection of both import sections and direct imports). These are distinct rule sets; none is deleted or silently selected here.

| Rule | Legacy module | Live app/workspace | Difference |
|---|---|---|---|
| Portfolio heat | `edge_core/risk_engine.py:32` 6% | `edge_workspace.py:81,103,414,596` 5% default | 6 vs 5 |
| Liquidity/ADTV | `edge_core/risk_engine.py:42-43,55-63` PASS ≥₹10Cr; CAUTION ≥₹2Cr | `edge_core/indian_risk_gates.py:5,36-38` and `edge_workspace.py:366-370` ≥₹5Cr | Different pass/caution bands |
| VCP windows | `edge_core/minervini_rules.py:58,76` 35/15/5, final ≤8% and declining volumes | `edge_workspace.py:70-76,344` disjoint 20/10/5, final ≤8%; volume ratio ≥1.5 | Window and volume criteria differ |
| Single position concentration | `edge_core/risk_engine.py:37` 8% weight | `edge_workspace.py:81,414` 10% default new-position notional | 8 vs 10 |
| Stop fallback | `edge_core/risk_engine.py:33` assumes 15% stop for missing stop | `edge_workspace.py:239-240,251-254` requires actual positive stops | Assumed vs mandatory |
| Volatility sizing | `edge_core/risk_engine.py:38-41` target 15% volatility, scaler 0.25–1.0, minimum 12 weeks | `edge_workspace.py:81-125` fixed-fractional sizing and risk gates | Different sizing mechanisms, not equivalent thresholds |
| Round-trip cost | `edge_core/risk_engine.py:46-48,66-71` base 0.40% plus 0.10% PASS or 0.50% CAUTION | `edge_workspace.py:81` 0.006 (0.6%) default; `edge_core/indian_risk_gates.py:42` 0.006 | 0.50%/0.90% vs 0.60% |
| Sector count | `edge_core/risk_engine.py:36,188` maximum three names per sector | `edge_workspace.py:81-125` does not enforce this sector-count cap in its sizing routine | Legacy-only cap |
| Drawdown gates | `edge_core/risk_engine.py:34-35` halve at 10%, stop at 15% | `edge_workspace.py:81-125` no equivalent drawdown parameter | Legacy-only thresholds |

Other legacy research values not automatically mapped to a live equivalent: `edge_core/minervini_rules.py:30-31` 30% above 52-week low / 75% of high; `edge_core/minervini_rules.py:38-48` 40/20/20/20 relative-strength weights. These require separate semantic review against `edge_core/analytics.py` and `edge_core/relative_strength.py` before claiming a numerical conflict.

**No threshold in this report is an instruction to change the live trading rules.**
