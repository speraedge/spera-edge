"""Universe definitions and official constituent loading for Momentum.

This module separates universe identity/source validation from Momentum math.
Frozen N500 behavior remains available through the NIFTY_500 spec. Future
universes must be added here rather than by changing the N500 constituent URL.
"""

from __future__ import annotations

from dataclasses import dataclass
import io
import time
from typing import Tuple

import pandas as pd
import requests


@dataclass(frozen=True)
class UniverseSpec:
    universe_id: str
    contract_id: str
    contract_version: str
    scope: str
    display_name: str
    urls: Tuple[str, ...]
    min_count: int
    max_count: int
    expected_count: int
    pass_min_count: int
    pass_max_count: int


NIFTY_500 = UniverseSpec(
    universe_id="NIFTY_500",
    contract_id="MOMENTUM_N500_V1",
    contract_version="1.0",
    scope="CURRENT_NIFTY_500",
    display_name="NIFTY 500",
    urls=(
        "https://nsearchives.nseindia.com/content/indices/ind_nifty500list.csv",
        "https://www.niftyindices.com/IndexConstituent/ind_nifty500list.csv",
    ),
    min_count=495,
    max_count=505,
    expected_count=500,
    pass_min_count=500,
    pass_max_count=500,
)


NIFTY_TOTAL_MARKET = UniverseSpec(
    universe_id="NIFTY_TOTAL_MARKET",
    contract_id="MOMENTUM_TOTAL_MARKET_V1",
    contract_version="1.0",
    scope="CURRENT_NIFTY_TOTAL_MARKET",
    display_name="NIFTY Total Market",
    urls=(
        "https://nsearchives.nseindia.com/content/indices/ind_niftytotalmarket_list.csv",
        "https://www.niftyindices.com/IndexConstituent/ind_niftytotalmarket_list.csv",
    ),
    # Official methodology targets NIFTY 500 + NIFTY Microcap 250. Temporary
    # corporate-action handling can create small count drift, so fail closed
    # outside a narrow safety band and mark non-750 counts REVIEW.
    min_count=745,
    max_count=755,
    expected_count=750,
    # Official NSE factsheets have shown temporary constituent counts above
    # the methodological target (for example 751 and 755 during 2026).
    # Treat current official 750-755 compositions as authoritative PASS while
    # retaining a narrow outer REVIEW/fail-closed safety band.
    pass_min_count=750,
    pass_max_count=755,
)


def _headers() -> dict:
    return {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ),
        "Accept": "text/csv,text/plain,*/*",
        "Connection": "close",
    }


def parse_constituent_csv(text: str, spec: UniverseSpec) -> tuple[pd.DataFrame, str]:
    if not text or len(text.strip()) < 100:
        raise ValueError(f"Official {spec.display_name} constituent CSV was empty/too small")

    df = pd.read_csv(io.StringIO(text))
    df.columns = [str(c).strip() for c in df.columns]

    if "Symbol" not in df.columns:
        raise ValueError(f"Official {spec.display_name} file does not contain Symbol column")

    industry_col = "Industry" if "Industry" in df.columns else "Sector"
    if industry_col not in df.columns:
        df["Industry"] = "Unknown"
        industry_col = "Industry"

    df = df.dropna(subset=["Symbol"]).copy()
    df["Symbol"] = df["Symbol"].astype(str).str.strip()
    df[industry_col] = df[industry_col].fillna("Unknown")

    duplicate_symbols = int(df["Symbol"].duplicated().sum())
    unique_symbols = int(df["Symbol"].nunique())
    if duplicate_symbols > 0:
        raise ValueError(
            f"Official {spec.display_name} universe contains "
            f"{duplicate_symbols} duplicate symbols"
        )
    # Two current symbols must never independently rank the same security.
    # Missing identities remain subject to the existing per-row trust gates.
    if "ISIN Code" in df.columns:
        identities = df["ISIN Code"].fillna("").astype(str).str.strip().str.upper()
        supplied = identities[identities.ne("") & ~identities.isin(("NAN", "NONE", "NULL", "-"))]
        if supplied.duplicated().any():
            raise ValueError(f"Official {spec.display_name} universe contains duplicate ISIN identities")
    if not (spec.min_count <= unique_symbols <= spec.max_count):
        raise ValueError(
            f"Official {spec.display_name} universe returned {unique_symbols} "
            f"unique symbols; accepted safety range is "
            f"{spec.min_count}-{spec.max_count}"
        )

    df.attrs["universe_id"] = spec.universe_id
    df.attrs["contract_id"] = spec.contract_id
    df.attrs["contract_version"] = spec.contract_version
    df.attrs["scope"] = spec.scope
    df.attrs["universe_count_status"] = (
        "PASS"
        if spec.pass_min_count <= unique_symbols <= spec.pass_max_count
        else "REVIEW"
    )
    return df, industry_col


def fetch_official_universe(
    spec: UniverseSpec,
    *,
    attempts_per_url: int = 3,
    connect_timeout_sec: int = 10,
    read_timeout_sec: int = 45,
) -> tuple[pd.DataFrame, str]:
    errors = []
    response = None
    source_url = None

    for url in spec.urls:
        for attempt in range(1, attempts_per_url + 1):
            try:
                r = requests.get(
                    url,
                    headers=_headers(),
                    timeout=(connect_timeout_sec, read_timeout_sec),
                )
                r.raise_for_status()
                response = r
                source_url = url
                break
            except Exception as exc:
                errors.append(
                    f"{url} attempt {attempt}/{attempts_per_url}: "
                    f"{type(exc).__name__}: {exc}"
                )
                if attempt < attempts_per_url:
                    time.sleep(min(2 ** (attempt - 1), 4))
        if response is not None:
            break

    if response is None:
        raise RuntimeError(
            f"All official {spec.display_name} constituent endpoints failed "
            f"after retries. " + " | ".join(errors[-6:])
        )

    df, industry_col = parse_constituent_csv(response.text, spec)
    df.attrs["universe_source_url"] = source_url
    return df, industry_col
