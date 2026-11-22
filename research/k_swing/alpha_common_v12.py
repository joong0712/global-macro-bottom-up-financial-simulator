"""K-SWING v1.2 shared, locked, no-future data contract.

All predictors are computed at T close or earlier. Historical outcome
labels are produced ONLY for 2019-2020 training candidates; 2021-22 is
already inspected development evaluation, NOT an untouched holdout.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from .data import load_calendar, validate_prices
from .vcr_experiment_v10 import sampled
from .vcr_strategy_v10 import _calendar

TRAIN_FIRST = pd.Timestamp("2019-01-01")
TRAIN_LAST = pd.Timestamp("2020-12-01")
LABEL_MATURITY_LAST = pd.Timestamp("2020-12-15")
EVAL_FIRST = pd.Timestamp("2021-01-01")
EVAL_LAST = pd.Timestamp("2022-12-15")
FEATURE_COLS = (
    "r1", "r3", "r5", "r10", "r20", "r60", "volatility20",
    "volume_ratio", "turnover_ratio", "to_ma20", "to_ma60",
    "near_high252", "range_close",
)


def load_screened_sample(data_dir: Path, modulus: int = 16):
    if modulus < 1:
        raise ValueError("Invalid modulus")
    audit_path = data_dir / "market_structure_quality.json"
    if not audit_path.is_file():
        raise ValueError("Historical market audit missing")
    audit = json.loads(audit_path.read_text(encoding="utf-8"))
    cal = audit.get("calendar", {})
    if cal.get("reference_only_dates") or cal.get("observed_only_dates"):
        raise ValueError("Unresolved historical KRX calendar discrepancy")
    private = data_dir / "_private"
    pieces = []
    for year in range(2017, 2023):
        file = private / f"kswing_screened_{year}.csv.gz"
        if not file.exists():
            raise FileNotFoundError(f"Screened year unavailable: {year}")
        for chunk in pd.read_csv(file, dtype={"ticker": "string"},
                                 parse_dates=["date"], chunksize=100_000):
            if "unsafe_session" not in chunk:
                raise ValueError("Unscreened OHLCV forbidden")
            mask = chunk.ticker.map(lambda code: sampled(code, modulus))
            if mask.any():
                pieces.append(chunk.loc[mask])
    if not pieces:
        raise ValueError("Selected securities empty")
    bars = validate_prices(pd.concat(pieces, ignore_index=True))
    dates = load_calendar(private / "krx_observed_sessions.csv", bars)
    _calendar(dates)
    if bars.date.max() > pd.Timestamp("2022-12-31"):
        raise ValueError("2023-2026 holdout data forbidden")
    return bars, dates


def screened_flags(x: pd.DataFrame):
    o, h, l, c, vol, turn = (x[k] for k in
                             ("open", "high", "low", "close", "volume", "turnover"))
    return (x.unsafe_session.eq(False)
            & x[["open", "high", "low", "close"]].gt(0).all(axis=1)
            & h.ge(x[["open", "low", "close"]].max(axis=1))
            & l.le(x[["open", "high", "close"]].min(axis=1))
            & vol.gt(0) & turn.gt(0))


def feature_panel(bars: pd.DataFrame, dates: pd.DatetimeIndex) -> pd.DataFrame:
    calendar = _calendar(dates)
    required = {"date", "ticker", "open", "high", "low", "close",
                "volume", "turnover", "unsafe_session"}
    if not required.issubset(bars) or bars.duplicated(["date", "ticker"]).any():
        raise ValueError("Must provide unique screened OHLCV")
    if bars.unsafe_session.isna().any() or not bars.unsafe_session.isin([True, False]).all():
        raise ValueError("Unsafe flag unknown")
    parts = []
    for ticker, group in bars.groupby("ticker", sort=True):
        if not group.date.isin(calendar).all():
            raise ValueError("Price bar outside the verified calendar")
        x = group.set_index("date").sort_index().reindex(calendar)
        safe = screened_flags(x)
        contiguous = safe.rolling(253, min_periods=253).sum().eq(253)
        c, h, lo, vol, t = (x[k] for k in ("close", "high", "low", "volume", "turnover"))
        previous_turn20 = t.shift(1).rolling(20, min_periods=20).mean()
        previous_vol20 = vol.shift(1).rolling(20, min_periods=20).mean()
        liq = (c.ge(1000) & t.ge(3e9) & previous_turn20.ge(3e9))
        p = pd.DataFrame({"date": calendar, "ticker": str(ticker),
                          "turnover": t.to_numpy()})
        vals = {
            "r1": c.pct_change(1, fill_method=None),
            "r3": c.pct_change(3, fill_method=None),
            "r5": c.pct_change(5, fill_method=None),
            "r10": c.pct_change(10, fill_method=None),
            "r20": c.pct_change(20, fill_method=None),
            "r60": c.pct_change(60, fill_method=None),
            "volatility20": c.pct_change(fill_method=None).rolling(20, min_periods=20).std(),
            "volume_ratio": vol.div(previous_vol20.where(previous_vol20.gt(0))),
            "turnover_ratio": t.div(previous_turn20.where(previous_turn20.gt(0))),
            "to_ma20": c.div(c.rolling(20, min_periods=20).mean()).sub(1),
            "to_ma60": c.div(c.rolling(60, min_periods=60).mean()).sub(1),
            "near_high252": c.div(h.shift(1).rolling(252, min_periods=252).max()),
            "range_close": c.sub(lo).div(h.sub(lo).replace(0, np.nan)),
        }
        for key, series in vals.items():
            p[key] = series.to_numpy()
        eligible = contiguous.to_numpy() & liq.to_numpy()
        finite = np.isfinite(p[list(FEATURE_COLS)].to_numpy(dtype=float)).all(axis=1)
        eligible &= finite
        if eligible.any():
            parts.append(p.loc[eligible])
    if not parts:
        return pd.DataFrame(columns=["date", "ticker", "turnover", *FEATURE_COLS])
    return pd.concat(parts, ignore_index=True).sort_values(
        ["date", "ticker"], kind="stable").reset_index(drop=True)


def training_bracket_labels(bars: pd.DataFrame,
                            training_candidates: pd.DataFrame,
                            dates: pd.DatetimeIndex, horizon: int) -> pd.DataFrame:
    """Match T+1 open, stop-first -3/+8 and 50bps charge, training only.

    Later sessions determine *labels* but are NEVER input features. Training
    labels must mature by LABEL_MATURITY_LAST, leaving a >10-session purge to
    January 2021 developmental evaluation. Uncertain bars are excluded.
    """
    calendar = _calendar(dates)
    if horizon not in (5, 10):
        raise ValueError("Only preregistered 5/10 session exits")
    if (not training_candidates.empty and
            (training_candidates.date.min() < TRAIN_FIRST
             or training_candidates.date.max() > TRAIN_LAST)):
        raise ValueError("Training features must remain in frozen 2019-2020 window")
    ix = {day: i for i, day in enumerate(calendar)}
    records = []
    groups = {str(ticker): g for ticker, g in bars.groupby("ticker")}
    half_fee = 50. / 20000.
    for ticker, rows in training_candidates.groupby("ticker"):
        x = groups[str(ticker)].set_index("date").sort_index().reindex(calendar)
        safe = screened_flags(x).to_numpy(dtype=bool)
        o, h, lo, c = (x[k].to_numpy(dtype=float) for k in
                        ("open", "high", "low", "close"))
        for day in rows.date:
            i = ix[pd.Timestamp(day)]
            if i + horizon >= len(calendar):
                continue
            if calendar[i + horizon] > LABEL_MATURITY_LAST or not safe[i]:
                continue
            entry = o[i + 1]
            if not np.isfinite(entry) or entry <= 0:
                continue
            stop, take = entry * .97, entry * 1.08
            resolved = None
            for k in range(1, horizon + 1):
                j = i + k
                if not safe[j]:
                    break
                if o[j] <= stop:
                    resolved = o[j]
                elif o[j] >= take:
                    resolved = o[j]
                elif lo[j] <= stop:
                    resolved = stop
                elif h[j] >= take:
                    resolved = take
                elif k == horizon:
                    resolved = c[j]
                if resolved is not None:
                    break
            if resolved is not None and np.isfinite(resolved):
                net = (resolved / entry) * ((1 - half_fee) / (1 + half_fee)) - 1
                records.append((day, str(ticker), float(net)))
    return pd.DataFrame(records, columns=["date", "ticker", "net_bracket_label"])


def assert_protected_eval_frame(frame: pd.DataFrame):
    if frame.empty or frame.date.min() < EVAL_FIRST or frame.date.max() > EVAL_LAST:
        raise ValueError("Evaluation must use 2021-2022 only; no locked period")
