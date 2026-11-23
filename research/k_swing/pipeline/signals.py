"""The three preregistered v24 scores. Higher score = buy. Only data <= T is used."""
from __future__ import annotations

import numpy as np
import pandas as pd

from .panel import Panel


def rev5(panel: Panel) -> pd.DataFrame:
    """H1 short-term reversal: minus the 5-session adjusted return."""
    return -(panel.adj_close / panel.adj_close.shift(5) - 1)


def high52(panel: Panel) -> pd.DataFrame:
    """H2 nearness to the 252-session adjusted high (1.0 = at the high)."""
    peak = panel.adj_high.rolling(252, min_periods=200).max()
    return panel.adj_close / peak


def lowvol(panel: Panel) -> pd.DataFrame:
    """H3 low volatility: minus the 60-session std of daily log returns (traded days only)."""
    log_ret = np.log(panel.adj_close / panel.adj_close.shift(1))
    log_ret = log_ret.where(panel.volume.gt(0) & panel.volume.shift(1).gt(0))
    return -log_ret.rolling(60, min_periods=50).std()


SCORES = {"REV5": rev5, "HIGH52": high52, "LOWVOL": lowvol}


def select(score: pd.DataFrame, eligible: pd.DataFrame, top_n: int) -> dict[pd.Timestamp, list[str]]:
    """Top-N codes per signal date among eligible codes with a finite score.

    Ties are broken by code so results are deterministic.
    """
    masked = score.where(eligible).replace([np.inf, -np.inf], np.nan)
    picks: dict[pd.Timestamp, list[str]] = {}
    for date, row in masked.iterrows():
        row = row.dropna()
        if row.empty:
            continue
        ordered = row.reset_index()
        ordered.columns = ["code", "score"]
        ordered = ordered.sort_values(["score", "code"], ascending=[False, True])
        picks[date] = ordered["code"].head(top_n).tolist()
    return picks
