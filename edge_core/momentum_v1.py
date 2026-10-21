"""Pure frozen Momentum V1 cross-sectional scoring.

This module contains no I/O, provider access, persistence or UI logic.
The same function is used by every universe-specific Momentum V1 contract so
formula drift between NIFTY 500 and NIFTY Total Market is impossible.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def _zscore(series: pd.Series) -> pd.Series:
    mean = series.mean()
    std = series.std()
    if pd.isna(std) or std <= 0:
        return pd.Series(np.nan, index=series.index)
    return (series - mean) / std


def _normalized_momentum_score(weighted_z: pd.Series) -> pd.Series:
    return pd.Series(
        np.where(weighted_z >= 0, 1.0 + weighted_z, 1.0 / (1.0 - weighted_z)),
        index=weighted_z.index,
        dtype=float,
    )


def apply_frozen_v1_scores(df: pd.DataFrame) -> pd.DataFrame:
    """Apply the frozen V1 ranking formula to one universe cross-section.

    Eligible rows are PASS or REVIEW rows with valid Ret_6M, Ret_12M and
    positive AnnVol. FAIL rows never receive a rank.

    The input is copied; callers retain ownership of their original frame.
    """
    out = df.copy()
    core_mask = (
        out["Data_Quality"].isin(["PASS", "REVIEW"])
        & pd.to_numeric(out["Ret_6M"], errors="coerce").notna()
        & pd.to_numeric(out["Ret_12M"], errors="coerce").notna()
        & pd.to_numeric(out["AnnVol"], errors="coerce").notna()
        & (pd.to_numeric(out["AnnVol"], errors="coerce") > 0)
    )

    out["MR6"] = np.nan
    out["MR12"] = np.nan
    out.loc[core_mask, "MR6"] = (
        out.loc[core_mask, "Ret_6M"]
    ) / out.loc[core_mask, "AnnVol"]
    out.loc[core_mask, "MR12"] = (
        out.loc[core_mask, "Ret_12M"]
    ) / out.loc[core_mask, "AnnVol"]

    out["Z6"] = np.nan
    out["Z12"] = np.nan
    out.loc[core_mask, "Z6"] = _zscore(out.loc[core_mask, "MR6"])
    out.loc[core_mask, "Z12"] = _zscore(out.loc[core_mask, "MR12"])

    out["Weighted_Z"] = np.nan
    out.loc[core_mask, "Weighted_Z"] = (
        0.5 * out.loc[core_mask, "Z6"]
        + 0.5 * out.loc[core_mask, "Z12"]
    )

    out["Normalized_Momentum_Score"] = np.nan
    out.loc[core_mask, "Normalized_Momentum_Score"] = (
        _normalized_momentum_score(out.loc[core_mask, "Weighted_Z"])
    )

    out["Percentile"] = np.nan
    out.loc[core_mask, "Percentile"] = (
        out.loc[core_mask, "Normalized_Momentum_Score"]
        .rank(method="average", pct=True)
        * 100.0
    )

    out["Pure_Momentum_Rank"] = np.nan
    out.loc[core_mask, "Pure_Momentum_Rank"] = (
        out.loc[core_mask, "Normalized_Momentum_Score"]
        .rank(method="min", ascending=False)
    )
    return out
