"""v25 single-portfolio rank-buffer backtest (see V25_PROTOCOL.md).

Decisions are made on the signal close T. In "close" mode they fill at the T close
(after-hours closing-price session); in "next_open" mode they fill at the T+1 open.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from . import config
from .backtest import last_row_index
from .panel import Panel

TOP_N = 20
BUFFER_K = 60


@dataclass
class Holding:
    code: str
    col: int
    units: float
    cost_basis: float
    entry_date: pd.Timestamp
    entry_adj_px: float
    value: float


@dataclass
class BufferResult:
    daily: pd.DataFrame
    trades: pd.DataFrame
    counters: dict
    turnover_one_way_per_year: float


def _ranks(score_row: np.ndarray, eligible_row: np.ndarray) -> np.ndarray:
    """1 = best; inf for ineligible / missing. Ties broken by column order (codes sorted)."""
    s = np.where(eligible_row & np.isfinite(score_row), score_row, -np.inf)
    order = np.lexsort((np.arange(len(s)), -s))
    ranks = np.empty(len(s))
    ranks[order] = np.arange(1, len(s) + 1)
    ranks[~np.isfinite(s)] = np.inf
    return ranks


def run_buffer(panel: Panel, score: pd.DataFrame, eligible: pd.DataFrame, avg_turnover: pd.DataFrame,
               signal_start: str, signal_end: str, mode: str = "close", zero_cost: bool = False,
               top_n: int = TOP_N, buffer_k: int = BUFFER_K) -> BufferResult:
    if mode not in ("close", "next_open"):
        raise ValueError("mode must be close or next_open")
    sessions = panel.sessions
    idx = np.where((sessions >= pd.Timestamp(signal_start)) & (sessions <= pd.Timestamp(signal_end)))[0]
    if len(idx) == 0:
        raise ValueError("no sessions in range")
    first, last = int(idx[0]), int(idx[-1])
    if mode == "next_open" and last + 1 >= len(sessions):
        last -= 1
    codes = list(panel.close.columns)
    close, open_, base = panel.close.to_numpy(), panel.open.to_numpy(), panel.base.to_numpy()
    vol, adj_close, adj_open = panel.volume.to_numpy(), panel.adj_close.to_numpy(), panel.adj_open.to_numpy()
    sc = score.reindex(index=sessions, columns=codes).to_numpy()
    el = eligible.reindex(index=sessions, columns=codes).fillna(False).to_numpy(dtype=bool)
    tov = avg_turnover.reindex(index=sessions, columns=codes).to_numpy()
    last_idx = last_row_index(panel)
    last_data_idx = len(sessions) - 1
    commission = 0.0 if zero_cost else config.COMMISSION

    def slip(t: int, c: int) -> float:
        return 0.0 if zero_cost else config.slippage(tov[t, c])

    def tax(t: int) -> float:
        return 0.0 if zero_cost else config.sell_tax(sessions[t])

    cash = 1.0
    holdings: dict[int, Holding] = {}
    trades, rows = [], []
    counters = {"buys": 0, "sells": 0, "blocked_buy": 0, "delayed_sell": 0, "delisted_exit": 0}
    bought_notional = 0.0
    pending: tuple[list[int], list[int], float, int] | None = None  # next_open: (sells, buys, alloc, decision_t)
    prev_equity = 1.0

    def sell(h: Holding, t: int, adj_px: float, s: float, reason: str) -> None:
        nonlocal cash
        proceeds = h.units * adj_px * (1 - s) * (1 - commission - tax(t))
        cash += proceeds
        trades.append({"code": h.code, "entry_date": h.entry_date, "exit_date": sessions[t],
                       "exit_reason": reason, "gross_return": adj_px / h.entry_adj_px - 1,
                       "net_return": proceeds / h.cost_basis - 1})
        counters["sells"] += 1
        del holdings[h.col]

    def buy(c: int, t: int, adj_px: float, s: float, alloc: float) -> None:
        nonlocal cash, bought_notional
        spend = min(alloc, cash)
        if spend <= 1e-12:
            return
        units = spend / (adj_px * (1 + s) * (1 + commission))
        cash -= spend
        bought_notional += spend / (alloc * top_n)
        holdings[c] = Holding(codes[c], c, units, spend, sessions[t], adj_px, units * adj_px)
        counters["buys"] += 1

    def decide(t: int) -> tuple[list[int], list[int], float]:
        ranks = _ranks(sc[t], el[t])
        sells = [c for c in holdings if ranks[c] > buffer_k]
        equity = cash + sum(h.value for h in holdings.values())
        candidates = [int(c) for c in np.argsort(ranks)[:top_n] if np.isfinite(ranks[c]) and c not in holdings]
        return sells, candidates, equity / top_n

    t = first
    end = last if mode == "close" else last + 1
    while t <= end:
        # Execute next_open decisions from the previous close.
        if mode == "next_open" and pending is not None:
            sells, buys, alloc, dt = pending
            for c in sells:
                if c not in holdings:
                    continue
                o, b = open_[t, c], base[t, c]
                if vol[t, c] > 0 and o > 0 and not (b > 0 and o / b - 1 <= -config.LIMIT_BAND):
                    sell(holdings[c], t, adj_open[t, c], slip(dt, c), "rank_exit")
                else:
                    counters["delayed_sell"] += 1
            for c in buys:
                if len(holdings) >= top_n:
                    break
                o, b = open_[t, c], base[t, c]
                if vol[t, c] > 0 and o > 0 and b > 0 and o / b - 1 < config.LIMIT_BAND:
                    buy(c, t, adj_open[t, c], slip(dt, c), alloc)
                else:
                    counters["blocked_buy"] += 1
            pending = None
        # Mark to market at the close.
        for h in holdings.values():
            px = adj_close[t, h.col]
            if np.isfinite(px):
                h.value = h.units * px
        # Delisting: last row reached before the end of the data.
        for h in list(holdings.values()):
            if t >= last_idx[h.col] and last_idx[h.col] < last_data_idx:
                sell(h, t, h.value / h.units, slip(t, h.col), "delisted")
                counters["delisted_exit"] += 1
        # Decide at this close.
        if t <= last:
            sells, candidates, alloc = decide(t)
            if mode == "close":
                for c in sells:
                    b = base[t, c]
                    tradable = vol[t, c] > 0 and np.isfinite(close[t, c])
                    if tradable and not (b > 0 and close[t, c] / b - 1 <= -config.LIMIT_BAND):
                        sell(holdings[c], t, adj_close[t, c], slip(t, c), "rank_exit")
                    else:
                        counters["delayed_sell"] += 1
                for c in candidates:
                    if len(holdings) >= top_n:
                        break
                    b = base[t, c]
                    if vol[t, c] > 0 and b > 0 and close[t, c] / b - 1 < config.LIMIT_BAND:
                        buy(c, t, adj_close[t, c], slip(t, c), alloc)
                    else:
                        counters["blocked_buy"] += 1
            else:
                pending = (sells, candidates, alloc, t)
        equity = cash + sum(h.value for h in holdings.values())
        prior = el[t - 1]
        r = adj_close[t][prior] / adj_close[t - 1][prior] - 1
        r = r[np.isfinite(r)]
        rows.append({"date": sessions[t], "strategy": equity / prev_equity - 1,
                     "benchmark": float(r.mean()) if len(r) else np.nan,
                     "invested": 1 - cash / equity if equity > 0 else 0.0, "names": len(holdings)})
        prev_equity = equity
        t += 1

    daily = pd.DataFrame(rows).set_index("date")
    daily["excess"] = daily["strategy"] - daily["benchmark"]
    years = len(daily) / 252
    return BufferResult(daily, pd.DataFrame(trades), counters, bought_notional / years if years else np.nan)
