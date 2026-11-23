"""Time-series inference on daily portfolio returns."""
from __future__ import annotations

import numpy as np
import pandas as pd

from . import config


def newey_west_t(x: np.ndarray, lag: int = config.NEWEY_WEST_LAG) -> float:
    x = np.asarray(x, dtype=float)
    x = x[np.isfinite(x)]
    n = len(x)
    if n < 3:
        return float("nan")
    e = x - x.mean()
    s = e @ e / n
    for k in range(1, min(lag, n - 1) + 1):
        w = 1 - k / (lag + 1)
        s += 2 * w * (e[k:] @ e[:-k]) / n
    if s <= 0:
        return float("nan")
    return float(x.mean() / np.sqrt(s / n))


def block_bootstrap_p(x: np.ndarray, block: int = config.BOOTSTRAP_BLOCK,
                      draws: int = config.BOOTSTRAP_DRAWS, seed: int = config.BOOTSTRAP_SEED) -> tuple[float, float, float]:
    """One-sided p for mean <= 0 via circular block bootstrap of the demeaned series.

    Returns (p_value, ci_low, ci_high) where the 95% CI is for the daily mean.
    """
    x = np.asarray(x, dtype=float)
    x = x[np.isfinite(x)]
    n = len(x)
    if n < block * 2:
        return float("nan"), float("nan"), float("nan")
    rng = np.random.default_rng(seed)
    blocks = int(np.ceil(n / block))
    starts = rng.integers(0, n, size=(draws, blocks))
    idx = (starts[:, :, None] + np.arange(block)[None, None, :]).reshape(draws, -1)[:, :n] % n
    means = x[idx].mean(axis=1)
    centered = means - x.mean()
    p = float((centered >= x.mean()).mean())
    lo, hi = np.quantile(means, [0.025, 0.975])
    return p, float(lo), float(hi)


def holm(p_values: dict[str, float], alpha: float = config.ALPHA) -> dict[str, dict]:
    items = sorted(((k, v) for k, v in p_values.items()), key=lambda kv: (np.nan_to_num(kv[1], nan=1.0), kv[0]))
    m = len(items)
    out, running, still = {}, 0.0, True
    for rank, (key, p) in enumerate(items):
        p = 1.0 if not np.isfinite(p) else p
        adj = min(1.0, max(running, (m - rank) * p))
        running = adj
        reject = still and adj < alpha
        if not reject:
            still = False
        out[key] = {"p": p, "p_holm": adj, "reject": bool(reject)}
    return out


def max_drawdown(returns: pd.Series) -> float:
    equity = (1 + returns.fillna(0)).cumprod()
    return float((equity / equity.cummax() - 1).min())


def summarize(daily: pd.DataFrame, trades: pd.DataFrame) -> dict:
    s, b, e = daily["strategy"], daily["benchmark"], daily["excess"]
    years = len(daily) / 252
    p, lo, hi = block_bootstrap_p(e.to_numpy())
    out = {
        "start": str(daily.index[0].date()), "end": str(daily.index[-1].date()), "sessions": len(daily),
        "strategy_cagr_pct": 100 * ((1 + s).prod() ** (1 / years) - 1),
        "benchmark_cagr_pct": 100 * ((1 + b.fillna(0)).prod() ** (1 / years) - 1),
        "strategy_mean_ann_pct": 100 * 252 * s.mean(),
        "excess_mean_ann_pct": 100 * 252 * e.mean(),
        "excess_ci95_ann_pct": [100 * 252 * lo, 100 * 252 * hi],
        "excess_p_bootstrap": p,
        "excess_t_newey_west": newey_west_t(e.to_numpy()),
        "strategy_sharpe": float(np.sqrt(252) * s.mean() / s.std()) if s.std() > 0 else float("nan"),
        "strategy_mdd_pct": 100 * max_drawdown(s),
        "avg_invested_pct": 100 * daily["invested"].mean(),
        "trades": int(len(trades)),
    }
    if len(trades):
        out.update({
            "trade_hit_rate_net_pct": 100 * float((trades["net_return"] > 0).mean()),
            "trade_mean_gross_pct": 100 * float(trades["gross_return"].mean()),
            "trade_mean_net_pct": 100 * float(trades["net_return"].mean()),
            "cost_per_trade_pct": 100 * float((trades["gross_return"] - trades["net_return"]).mean()),
        })
    yearly = daily.groupby(daily.index.year).agg(
        strategy=("strategy", lambda r: (1 + r).prod() - 1),
        benchmark=("benchmark", lambda r: (1 + r.fillna(0)).prod() - 1),
        excess_mean_ann=("excess", lambda r: 252 * r.mean()))
    out["yearly_pct"] = {int(y): {k: round(100 * float(v), 3) for k, v in row.items()} for y, row in yearly.iterrows()}
    return out
