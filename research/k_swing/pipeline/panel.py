"""Wide (date x code) market panel with KRX base-price adjustment and the v24 universe."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from . import config

RAW_COLUMNS = ("Date", "Code", "Name", "Market", "Dept", "Open", "High", "Low", "Close",
               "Changes", "Volume", "Amount")


@dataclass
class Panel:
    """All frames share the same DatetimeIndex (sessions) and columns (codes)."""
    open: pd.DataFrame        # raw, NaN when not traded
    high: pd.DataFrame
    low: pd.DataFrame
    close: pd.DataFrame       # raw, NaN when the code has no row that day
    base: pd.DataFrame        # KRX base (reference) price = Close - Changes
    volume: pd.DataFrame
    amount: pd.DataFrame
    eligible_static: pd.DataFrame  # market / share class / dept / name filter per day
    factor: pd.DataFrame      # corporate-action factor f_t (1.0 when none)
    adj_open: pd.DataFrame
    adj_high: pd.DataFrame
    adj_low: pd.DataFrame
    adj_close: pd.DataFrame

    @property
    def sessions(self) -> pd.DatetimeIndex:
        return self.close.index

    @property
    def traded(self) -> pd.DataFrame:
        return self.volume.gt(0) & self.open.gt(0)


def read_marcap(files: list[Path]) -> pd.DataFrame:
    frames = []
    for path in files:
        frame = pd.read_parquet(path, columns=list(RAW_COLUMNS))
        frames.append(frame)
    raw = pd.concat(frames, ignore_index=True)
    raw["Date"] = pd.to_datetime(raw["Date"]).dt.normalize()
    if (raw["Date"] >= config.LOCKED_FROM).any():
        raise ValueError("2026 holdout data supplied; v24 never reads it")
    raw = raw.loc[raw["Market"].isin(["KOSPI", "KOSDAQ"])].copy()
    raw["Code"] = raw["Code"].astype(str)
    if raw.duplicated(["Date", "Code"]).any():
        raise ValueError("duplicate code/date rows")
    return raw


def static_filter(raw: pd.DataFrame) -> pd.Series:
    """Per-row share-class / segment exclusions (row-level so designations can change)."""
    dept = raw["Dept"].fillna("").astype(str)
    name = raw["Name"].fillna("").astype(str)
    ok = raw["Code"].str.fullmatch(config.COMMON_SHARE_CODE)
    for word in config.EXCLUDED_DEPT_KEYWORDS:
        ok &= ~dept.str.contains(word, regex=False)
    for word in config.EXCLUDED_NAME_KEYWORDS:
        ok &= ~name.str.contains(word, regex=False)
    return ok.fillna(False)


def adjustment_factors(close: pd.DataFrame, base: pd.DataFrame) -> pd.DataFrame:
    """f_t = base_t / previous available close; 1.0 unless it differs by > tolerance."""
    prev_close = close.ffill().shift(1)
    f = base / prev_close
    f = f.where(f.gt(0) & np.isfinite(f))
    changed = f.sub(1).abs().gt(config.ADJUST_TOLERANCE)
    return f.where(changed, 1.0).fillna(1.0)


def backward_multiplier(factor: pd.DataFrame) -> pd.DataFrame:
    """Multiplier for prices at t: product of all factors strictly after t."""
    reverse_cum = factor.iloc[::-1].cumprod().iloc[::-1]
    return reverse_cum.shift(-1).fillna(1.0)


def build_panel(raw: pd.DataFrame) -> Panel:
    raw = raw.copy()
    raw["static_ok"] = static_filter(raw)

    def wide(column: str) -> pd.DataFrame:
        return raw.pivot(index="Date", columns="Code", values=column).sort_index()

    close = wide("Close").astype(float)
    sessions, codes = close.index, close.columns

    def aligned(column: str) -> pd.DataFrame:
        return wide(column).reindex(index=sessions, columns=codes)

    volume = aligned("Volume").astype(float)
    amount = aligned("Amount").astype(float)
    traded = volume.gt(0)
    open_ = aligned("Open").astype(float)
    high = aligned("High").astype(float)
    low = aligned("Low").astype(float)
    for frame in (open_, high, low):
        frame.mask(~traded | frame.le(0), inplace=True)
    changes = aligned("Changes").astype(float)
    base = close - changes
    static_ok = aligned("static_ok").eq(True)

    factor = adjustment_factors(close, base)
    mult = backward_multiplier(factor)
    return Panel(
        open=open_, high=high, low=low, close=close, base=base, volume=volume, amount=amount,
        eligible_static=static_ok, factor=factor,
        adj_open=open_ * mult, adj_high=high * mult, adj_low=low * mult, adj_close=close * mult,
    )


def universe(panel: Panel, settings: config.Settings) -> pd.DataFrame:
    """Boolean eligibility at signal close T (uses data <= T only)."""
    present = panel.close.notna()
    history = present.cumsum()
    traded = panel.volume.gt(0)
    active = traded.rolling(20, min_periods=20).sum()
    avg_turnover = panel.amount.where(present).fillna(0).rolling(20, min_periods=20).mean()
    return (
        panel.eligible_static
        & traded
        & panel.close.ge(settings.min_price)
        & active.ge(settings.min_active_days)
        & avg_turnover.ge(settings.min_turnover)
        & history.ge(settings.min_history)
    )


def average_turnover(panel: Panel) -> pd.DataFrame:
    present = panel.close.notna()
    return panel.amount.where(present).fillna(0).rolling(20, min_periods=20).mean()


def daily_adjusted_returns(panel: Panel) -> pd.DataFrame:
    """Close-to-close adjusted returns; NaN where either day has no row."""
    return panel.adj_close / panel.adj_close.shift(1) - 1
