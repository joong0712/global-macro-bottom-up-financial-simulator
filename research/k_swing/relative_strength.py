"""Market/sector-relative strength features; require genuine dated benchmarks.

No sector classification is inferred from ticker, and no missing benchmark
prices are forward-filled. Handles incomplete security date sequences.
"""
from __future__ import annotations
import numpy as np
import pandas as pd


def compute_relative_strength(stocks: pd.DataFrame, benchmarks: pd.DataFrame,
                              windows: tuple[int, ...] = (5, 10, 20, 60)) -> pd.DataFrame:
    stock_cols = {"date", "ticker", "close", "market_benchmark_id", "sector_benchmark_id"}
    bench_cols = {"date", "benchmark_id", "close"}
    if not stock_cols.issubset(stocks.columns) or not bench_cols.issubset(benchmarks.columns):
        raise ValueError("stock and benchmark dates/identifiers/closing prices required")
    if not windows or any(not isinstance(n, int) or n < 1 for n in windows):
        raise ValueError("windows must be positive integers")
    if len(set(windows)) != len(windows):
        raise ValueError("duplicate lookback windows")
    s, b = stocks.copy(), benchmarks.copy()
    s["date"] = pd.to_datetime(s.date, errors="raise").dt.normalize()
    b["date"] = pd.to_datetime(b.date, errors="raise").dt.normalize()
    if s.duplicated(["ticker", "date"]).any() or b.duplicated(["benchmark_id", "date"]).any():
        raise ValueError("duplicate daily security or benchmark")
    if s[["date", "ticker"]].isna().any().any() or b[["date", "benchmark_id"]].isna().any().any():
        raise ValueError("missing dates or IDs")
    if (pd.to_numeric(s.close, errors="coerce").dropna() <= 0).any() or (pd.to_numeric(b.close, errors="coerce").dropna() <= 0).any():
        raise ValueError("nonpositive closes")
    s["close"] = pd.to_numeric(s.close, errors="coerce")
    b["close"] = pd.to_numeric(b.close, errors="coerce")
    s["_row_order"] = np.arange(len(s))
    for label, key in (("market", "market_benchmark_id"), ("sector", "sector_benchmark_id")):
        source = b.rename(columns={"benchmark_id": key, "close": label + "_close"})
        s = s.merge(source, on=["date", key], how="left", validate="many_to_one")
    # The global benchmark session union catches ticker-specific missing days.
    calendar = pd.Series(range(b.date.nunique()), index=pd.DatetimeIndex(sorted(b.date.unique())))
    s = s.sort_values(["ticker", "date"]).reset_index(drop=True)
    s["_session_id"] = s.date.map(calendar)
    if s["_session_id"].isna().any():
        raise ValueError("security date absent in supplied benchmark calendar")
    results = []
    for _, g in s.groupby("ticker", sort=False):
        g = g.copy()
        for n in windows:
            contiguous = g["_session_id"].sub(g["_session_id"].shift(n)).eq(n)
            close_ok = g.close.rolling(n + 1, min_periods=n + 1).count().eq(n + 1)
            security_return = g.close.div(g.close.shift(n))
            for label, key in (("market", "market_benchmark_id"), ("sector", "sector_benchmark_id")):
                bench = g[label + "_close"]
                bench_ok = bench.rolling(n + 1, min_periods=n + 1).count().eq(n + 1)
                same_id = g[key].eq(g[key].shift(1)).rolling(n, min_periods=n).sum().eq(n)
                g[f"rs_{label}_{n}"] = (
                    security_return.div(bench.div(bench.shift(n))).sub(1)
                ).where(contiguous & close_ok & bench_ok & same_id)
        stock_return = g.close.pct_change(fill_method=None)
        market_return = g.market_close.pct_change(fill_method=None)
        joined = stock_return.notna() & market_return.notna() & (
            g.market_benchmark_id.eq(g.market_benchmark_id.shift(1))
        ) & g["_session_id"].diff().eq(1)
        market_ret = market_return.where(joined)
        stock_ret = stock_return.where(joined)
        cov = stock_ret.rolling(60, min_periods=60).cov(market_ret)
        var = market_ret.rolling(60, min_periods=60).var()
        g["market_beta_60"] = cov.div(var.where(var.gt(0)))
        results.append(g)
    z = pd.concat(results, ignore_index=True)
    features = [f"rs_{label}_{n}" for label in ("market", "sector") for n in windows]
    return z.sort_values("_row_order")[["date", "ticker", *features, "market_beta_60"]].reset_index(drop=True)
