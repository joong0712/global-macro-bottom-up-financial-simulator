"""Five preregistered Ichimoku/SMA entry signals and a v1.1 VCR control.

Every T-close decision uses only OHLCV through T. Ichimoku cloud at T
comes from 26 sessions earlier (.shift(+26) in a chronological Series),
NOT from a forward-shifted signal using future data. The Chikou display
is deliberately excluded. No 2023-2026 dates are admitted.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .vcr_strategy_v10 import _calendar, VCRConfig, symbol_signal_flags

METHODS = (
    "ichi_cloud_breakout", "ichi_kijun_reclaim", "ma_5x20",
    "ma20_reclaim", "ichi_ma_confirm", "vcr_trend_control",
)


def indicator_frame(symbol: pd.DataFrame, calendar: pd.DatetimeIndex) -> pd.DataFrame:
    dates = _calendar(calendar)
    required = {"date", "ticker", "open", "high", "low", "close",
                "volume", "turnover", "unsafe_session"}
    if not required.issubset(symbol) or symbol.empty or symbol.ticker.nunique() != 1:
        raise ValueError("Exactly one screened security and complete OHLCV required")
    s = symbol.copy()
    s.date = pd.to_datetime(s.date).dt.normalize()
    if s.date.duplicated().any() or not s.date.isin(dates).all():
        raise ValueError("Price dates duplicated or outside locked exchange calendar")
    if s.unsafe_session.isna().any() or not s.unsafe_session.isin([True, False]).all():
        raise ValueError("Unknown corporate action bar quality")
    x = s.set_index("date").sort_index().reindex(dates)
    o, h, l, c, v, t = (pd.to_numeric(x[k], errors="coerce") for k in
                        ("open", "high", "low", "close", "volume", "turnover"))
    safe = (o.gt(0) & h.gt(0) & l.gt(0) & c.gt(0)
            & h.ge(pd.concat([o, l, c], axis=1).max(axis=1))
            & l.le(pd.concat([o, h, c], axis=1).min(axis=1))
            & v.gt(0) & t.gt(0) & x.unsafe_session.eq(False))
    clean253 = safe.rolling(253, min_periods=253).sum().eq(253)
    previous_turn20 = t.shift(1).rolling(20, min_periods=20).mean()
    elig = clean253 & c.ge(1000) & t.ge(3e9) & previous_turn20.ge(3e9)

    # Standard 9/26/52 Tenkan/Kijun/Senkou, with the *visible at T*
    # cloud based on values computed at T-26, not an advance leak.
    mid9 = (h.rolling(9, min_periods=9).max()
            + l.rolling(9, min_periods=9).min()) / 2
    mid26 = (h.rolling(26, min_periods=26).max()
             + l.rolling(26, min_periods=26).min()) / 2
    mid52 = (h.rolling(52, min_periods=52).max()
             + l.rolling(52, min_periods=52).min()) / 2
    span_a_visible = ((mid9 + mid26) / 2).shift(26)
    span_b_visible = mid52.shift(26)
    top = pd.concat([span_a_visible, span_b_visible], axis=1).max(axis=1)
    bottom = pd.concat([span_a_visible, span_b_visible], axis=1).min(axis=1)
    cloud_ready = span_a_visible.notna() & span_b_visible.notna()
    top = top.where(cloud_ready)
    bottom = bottom.where(cloud_ready)
    sma5 = c.rolling(5, min_periods=5).mean()
    sma20 = c.rolling(20, min_periods=20).mean()
    sma60 = c.rolling(60, min_periods=60).mean()
    out = pd.DataFrame({
        "close": c, "volume": v, "turnover": t,
        "eligible": elig, "tenkan": mid9, "kijun": mid26,
        "cloud_a": span_a_visible, "cloud_b": span_b_visible,
        "cloud_top": top, "cloud_bottom": bottom,
        "sma5": sma5, "sma20": sma20, "sma60": sma60,
    }, index=dates)
    return out


def symbol_timing_candidates(symbol: pd.DataFrame,
                             calendar: pd.DatetimeIndex) -> pd.DataFrame:
    dates = _calendar(calendar)
    x = indicator_frame(symbol, dates)
    c, ten, kij, cloud, m5, m20, m60 = (
        x.close, x.tenkan, x.kijun, x.cloud_top,
        x.sma5, x.sma20, x.sma60)
    cloud_break = (c.shift(1).le(cloud.shift(1))
                   & c.gt(cloud) & ten.gt(kij)
                   & x.cloud_a.ge(x.cloud_b))
    kij_reclaim = (c.shift(1).le(kij.shift(1))
                   & c.gt(kij) & c.gt(cloud)
                   & ten.ge(kij))
    golden = (m5.shift(1).le(m20.shift(1))
              & m5.gt(m20) & m20.gt(m60) & c.gt(m60))
    ma_reclaim = (c.shift(1).le(m20.shift(1))
                  & c.gt(m20) & m20.gt(m60)
                  & m60.gt(m60.shift(5)))
    confluence = cloud_break & m20.gt(m60) & c.gt(m20)
    vcr = symbol_signal_flags(symbol, dates, VCRConfig())
    highs = symbol.copy()
    highs.date = pd.to_datetime(highs.date).dt.normalize()
    prior_high252 = (highs.set_index("date").sort_index().reindex(dates)
                     .high.shift(1).rolling(252, min_periods=252).max())
    vcr_base = (pd.Series(vcr.vcr.to_numpy(dtype=bool), index=dates)
                & c.div(c.shift(60)).ge(1.10)
                & c.div(prior_high252.where(prior_high252.gt(0))).ge(.80))
    masks = {
        "ichi_cloud_breakout": cloud_break,
        "ichi_kijun_reclaim": kij_reclaim,
        "ma_5x20": golden,
        "ma20_reclaim": ma_reclaim,
        "ichi_ma_confirm": confluence,
        "vcr_trend_control": vcr_base,
    }
    # Lower score wins a day's ranking, based only on price information at T.
    # Scores are fixed before experiment and are never fitted to future PnL.
    scores = {
        "ichi_cloud_breakout": -c.div(cloud).sub(1),
        "ichi_kijun_reclaim": -c.div(kij).sub(1),
        "ma_5x20": -m5.div(m20).sub(1),
        "ma20_reclaim": -c.div(m20).sub(1),
        "ichi_ma_confirm": -c.div(cloud).sub(1),
        "vcr_trend_control": -c.div(m20).sub(1),
    }
    parts = []
    ticker = str(symbol.ticker.iloc[0])
    for name in METHODS:
        score = scores[name].replace([np.inf, -np.inf], np.nan)
        mask = x.eligible & masks[name].fillna(False) & score.notna()
        if not mask.any():
            continue
        sub = pd.DataFrame({"date": dates, "ticker": ticker,
                            "turnover": x.turnover.to_numpy(),
                            "score": score.to_numpy()}, index=dates).loc[mask]
        sub = sub.copy()
        sub["strategy"] = name
        parts.append(sub.reset_index(drop=True))
    if not parts:
        return pd.DataFrame(columns=["date", "ticker", "turnover", "score", "strategy"])
    return pd.concat(parts, ignore_index=True)


def build_timing_candidates(bars: pd.DataFrame, calendar: pd.DatetimeIndex):
    dates = _calendar(calendar)
    if bars.empty or not {"date", "ticker"}.issubset(bars):
        raise ValueError("Historical screened prices missing")
    parts = []
    for _, group in bars.groupby("ticker", sort=True):
        rows = symbol_timing_candidates(group, dates)
        if not rows.empty:
            parts.append(rows)
    if not parts:
        return pd.DataFrame(columns=["date", "ticker", "turnover", "score", "strategy"])
    return pd.concat(parts, ignore_index=True).sort_values(
        ["date", "strategy", "score", "ticker"], kind="stable").reset_index(drop=True)
