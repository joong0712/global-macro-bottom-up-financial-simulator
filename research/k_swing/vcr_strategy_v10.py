"""VCR v1.0: past-only compression -> T-close breakout research signals.

No future labels, live trading, historical-security verification, or holdout access.
"""
from __future__ import annotations

from dataclasses import dataclass
import numpy as np
import pandas as pd

STRATEGIES = ("breakout", "breakout_volume", "vcr")
LAST_RESEARCH_SESSION = pd.Timestamp("2022-12-31")


@dataclass(frozen=True)
class VCRConfig:
    bb_window: int = 20
    percentile_window: int = 120
    compression_quantile: float = .20
    breakout_window: int = 20
    volume_window: int = 20
    volume_multiplier: float = 1.8
    min_mean_turnover_krw: float = 3_000_000_000
    min_signal_turnover_krw: float = 3_000_000_000

    def __post_init__(self):
        if (min(self.bb_window, self.percentile_window, self.breakout_window,
                self.volume_window) < 2 or not 0 < self.compression_quantile < 1
                or self.volume_multiplier <= 0 or self.min_mean_turnover_krw < 0
                or self.min_signal_turnover_krw < 0):
            raise ValueError("Invalid VCR parameters")


def _calendar(calendar: pd.DatetimeIndex) -> pd.DatetimeIndex:
    dates = pd.DatetimeIndex(calendar).normalize()
    if (len(dates) < 2 or dates.has_duplicates or not dates.is_monotonic_increasing
            or dates.tz is not None or dates.max() > LAST_RESEARCH_SESSION):
        raise ValueError("Trading calendar invalid or 2023-2026 holdouts locked")
    return dates


def symbol_signal_flags(symbol: pd.DataFrame, calendar: pd.DatetimeIndex,
                        cfg: VCRConfig = VCRConfig()) -> pd.DataFrame:
    """Reindex one stock on the exchange calendar; only information through T.

    Compression at T uses BB width at T-1 and a 120-session window ENDING T-1.
    Breakout at T compares close(T) to highs T-20..T-1, never high(T).
    Every baseline shares the full VCR warmup/quality/turnover universe.
    """
    dates = _calendar(calendar)
    required = {"date", "ticker", "open", "high", "low", "close", "volume",
                "turnover", "unsafe_session"}
    if not required.issubset(symbol):
        raise ValueError("Screened OHLCV and unsafe_session are required")
    if symbol.empty or symbol.ticker.nunique() != 1:
        raise ValueError("Exactly one stock required")
    s = symbol.copy()
    s["date"] = pd.to_datetime(s.date).dt.normalize()
    if s.date.duplicated().any() or not s.date.isin(dates).all():
        raise ValueError("Duplicate or out-of-calendar stock bars")
    if s["unsafe_session"].isna().any() or not s["unsafe_session"].isin([True, False]).all():
        raise ValueError("Unsafe-session flags must be verified booleans")
    x = s.set_index("date").sort_index().reindex(dates)
    for col in ("open", "high", "low", "close", "volume", "turnover"):
        x[col] = pd.to_numeric(x[col], errors="coerce")
    c, h, v, t = x.close, x.high, x.volume, x.turnover
    valid_bar = (x[["open", "high", "low", "close"]].gt(0).all(axis=1)
                 & h.ge(x[["open", "close", "low"]].max(axis=1))
                 & x.low.le(x[["open", "close", "high"]].min(axis=1))
                 & v.gt(0) & t.gt(0) & x.unsafe_session.eq(False))
    # Complete path since first BB observation needed for 120-band history.
    warmup = cfg.bb_window + cfg.percentile_window - 1
    clean = valid_bar.rolling(warmup, min_periods=warmup).sum().eq(warmup)
    ma = c.rolling(cfg.bb_window, min_periods=cfg.bb_window).mean()
    std = c.rolling(cfg.bb_window, min_periods=cfg.bb_window).std(ddof=0)
    width = (4 * std / ma.where(ma.gt(0))).replace([np.inf, -np.inf], np.nan)
    old_width = width.shift(1)
    threshold = old_width.rolling(cfg.percentile_window,
                                  min_periods=cfg.percentile_window).quantile(cfg.compression_quantile)
    compressed = old_width.le(threshold) & threshold.notna()
    prior_high = h.shift(1).rolling(cfg.breakout_window,
                                     min_periods=cfg.breakout_window).max()
    breakout = c.gt(prior_high) & prior_high.gt(0)
    old_volume = v.shift(1).rolling(cfg.volume_window,
                                    min_periods=cfg.volume_window).mean()
    ratio = (v / old_volume.where(old_volume.gt(0))).replace([np.inf, -np.inf], np.nan)
    liquid = (t.shift(1).rolling(cfg.volume_window,
                                 min_periods=cfg.volume_window).mean().ge(cfg.min_mean_turnover_krw)
              & t.ge(cfg.min_signal_turnover_krw))
    eligible = clean & liquid & threshold.notna() & prior_high.notna() & ratio.notna()
    b = eligible & breakout
    bv = b & ratio.ge(cfg.volume_multiplier)
    vc = bv & compressed
    # Lowest score is top-ranked by the legacy cash simulator. Do not use future outcomes.
    strength = ((c / prior_high - 1).clip(lower=0) * np.log1p(ratio.clip(lower=0)))
    out = pd.DataFrame({
        "date": dates, "ticker": str(s.ticker.iloc[0]),
        "turnover": t.to_numpy(), "score": (-strength).to_numpy(),
        "breakout": b.to_numpy(dtype=bool),
        "breakout_volume": bv.to_numpy(dtype=bool),
        "vcr": vc.to_numpy(dtype=bool),
    })
    return out


def build_signals(bars: pd.DataFrame, calendar: pd.DatetimeIndex,
                  cfg: VCRConfig = VCRConfig(),
                  first_signal: str = "2019-01-01") -> pd.DataFrame:
    """Return strategy-labelled T-close signals, without securities' future data."""
    dates = _calendar(calendar)
    if not {"date", "ticker"}.issubset(bars):
        raise ValueError("Missing bars date/ticker")
    if bars.empty:
        raise ValueError("No screened bars")
    parts = []
    cutoff = pd.Timestamp(first_signal)
    if cutoff > LAST_RESEARCH_SESSION:
        raise ValueError("2023-2026 holdouts locked")
    for _, symbol in bars.groupby("ticker", sort=True):
        f = symbol_signal_flags(symbol, dates, cfg)
        for name in STRATEGIES:
            hits = f.loc[f[name] & f.date.ge(cutoff),
                         ["date", "ticker", "turnover", "score"]].copy()
            if len(hits):
                hits["strategy"] = name
                parts.append(hits)
    if not parts:
        return pd.DataFrame(columns=["date", "ticker", "turnover", "score", "strategy"])
    return pd.concat(parts, ignore_index=True).sort_values(
        ["date", "strategy", "score", "ticker"], kind="stable").reset_index(drop=True)
