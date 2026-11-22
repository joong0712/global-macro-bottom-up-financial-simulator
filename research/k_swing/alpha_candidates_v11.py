"""Three predeclared return-focused 1-2 week signals and a VCR control.

Uses T-close information only, a common 253-session clean lookback, and
the K-SWING 2023-2026 lock. Research only, never a brokerage order.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from .vcr_strategy_v10 import VCRConfig, _calendar, symbol_signal_flags

METHODS = ("momentum52", "reversal3", "vcr_trend", "vcr_control")
MIN_TURNOVER = 3_000_000_000
QUALITY_LOOKBACK = 253


def symbol_candidates(symbol: pd.DataFrame, calendar: pd.DatetimeIndex) -> pd.DataFrame:
    dates = _calendar(calendar)
    required = {"date", "ticker", "open", "high", "low", "close",
                "volume", "turnover", "unsafe_session"}
    if not required.issubset(symbol) or symbol.empty or symbol.ticker.nunique() != 1:
        raise ValueError("Single screened OHLCV security required")
    s = symbol.copy()
    s["date"] = pd.to_datetime(s.date).dt.normalize()
    if s.date.duplicated().any() or not s.date.isin(dates).all():
        raise ValueError("Duplicate or out-of-calendar stock bars")
    if s.unsafe_session.isna().any() or not s.unsafe_session.isin([True, False]).all():
        raise ValueError("Unknown unsafe_session state")
    x = s.set_index("date").sort_index().reindex(dates)
    for field in ("open", "high", "low", "close", "volume", "turnover"):
        x[field] = pd.to_numeric(x[field], errors="coerce")
    close, high, low, vol, turnover = (
        x.close, x.high, x.low, x.volume, x.turnover)
    safe = (x[["open", "high", "low", "close"]].gt(0).all(axis=1)
            & high.ge(x[["open", "close", "low"]].max(axis=1))
            & low.le(x[["open", "close", "high"]].min(axis=1))
            & vol.gt(0) & turnover.gt(0) & x.unsafe_session.eq(False))
    common_history = safe.rolling(QUALITY_LOOKBACK,
                                   min_periods=QUALITY_LOOKBACK).sum().eq(QUALITY_LOOKBACK)
    avg_turnover20 = turnover.shift(1).rolling(20, min_periods=20).mean()
    avg_volume20 = vol.shift(1).rolling(20, min_periods=20).mean()
    vr = (vol / avg_volume20.where(avg_volume20.gt(0))).replace(
        [np.inf, -np.inf], np.nan)
    common = (common_history & close.ge(1000)
              & avg_turnover20.ge(MIN_TURNOVER)
              & turnover.ge(MIN_TURNOVER) & vr.notna())
    prior_high252 = high.shift(1).rolling(252, min_periods=252).max()
    near_high = close / prior_high252.where(prior_high252.gt(0))
    mom60 = close.div(close.shift(60)).sub(1)
    sma20 = close.rolling(20, min_periods=20).mean()
    sma60 = close.rolling(60, min_periods=60).mean()
    ret3 = close.div(close.shift(3)).sub(1)

    m52 = (common & near_high.ge(.95) & mom60.ge(.12)
           & close.gt(sma20) & vr.ge(1.2))
    score_m52 = -(0.7 * near_high + 0.3 * mom60.clip(-1, 2)
                  + 0.1 * vr.clip(0, 5))
    rev = (common & ret3.le(-.07) & mom60.ge(.05)
           & close.ge(sma60.mul(.85)) & vr.ge(1.3))
    score_rev = ret3 - .1 * mom60

    vcr = symbol_signal_flags(symbol, dates, VCRConfig())
    base = common & pd.Series(vcr.vcr.to_numpy(dtype=bool), index=dates)
    trend = base & mom60.ge(.10) & near_high.ge(.80)
    score_base = pd.Series(vcr.score.to_numpy(dtype=float), index=dates)
    score_trend = score_base - .2 * mom60

    masks = {"momentum52": m52, "reversal3": rev,
             "vcr_trend": trend, "vcr_control": base}
    scores = {"momentum52": score_m52, "reversal3": score_rev,
              "vcr_trend": score_trend, "vcr_control": score_base}
    result = []
    for name in METHODS:
        mask = masks[name].fillna(False) & scores[name].notna()
        sub = pd.DataFrame({"date": dates, "ticker": str(s.ticker.iloc[0]),
                            "turnover": turnover.to_numpy(),
                            "score": scores[name].to_numpy()})
        sub = sub.loc[mask.to_numpy()].copy()
        if len(sub):
            sub["strategy"] = name
            result.append(sub)
    if not result:
        return pd.DataFrame(columns=["date", "ticker", "turnover", "score", "strategy"])
    return pd.concat(result, ignore_index=True)


def build_candidates(bars: pd.DataFrame, calendar: pd.DatetimeIndex,
                     first_signal: str = "2019-01-01") -> pd.DataFrame:
    dates = _calendar(calendar)
    if pd.Timestamp(first_signal) > pd.Timestamp("2022-12-31"):
        raise ValueError("2023-2026 holdouts locked")
    if bars.empty or not {"date", "ticker"}.issubset(bars):
        raise ValueError("No securities")
    parts = []
    for _, symbol in bars.groupby("ticker", sort=True):
        x = symbol_candidates(symbol, dates)
        if len(x):
            parts.append(x.loc[x.date.ge(pd.Timestamp(first_signal))])
    if not parts:
        return pd.DataFrame(columns=["date", "ticker", "turnover", "score", "strategy"])
    return pd.concat(parts, ignore_index=True).sort_values(
        ["date", "strategy", "score", "ticker"], kind="stable").reset_index(drop=True)
