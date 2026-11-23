"""Sleeve-based account simulation for overlapping H-day cohorts (Jegadeesh-Titman style).

Each of H sleeves starts with 1/H of capital. Sleeve j invests on signal dates whose
session offset is j mod H, buying up to N equal slots at the next open with whatever
cash it has. Positions are sold at the planned exit close, or later if the stock is
halted / locked limit-down, or at the last close if the stock disappears (delisting).
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from . import config
from .panel import Panel


@dataclass
class Position:
    sleeve: int
    code: str
    col: int
    signal_date: pd.Timestamp
    entry_idx: int
    planned_exit_idx: int
    units: float
    entry_adj_open: float
    cost_basis: float
    slip: float
    value: float
    last_close_idx: int


@dataclass
class Result:
    daily: pd.DataFrame            # account and benchmark daily returns
    trades: pd.DataFrame
    counters: dict = field(default_factory=dict)


def _arrays(panel: Panel):
    return {
        "open": panel.open.to_numpy(),
        "close": panel.close.to_numpy(),
        "base": panel.base.to_numpy(),
        "volume": panel.volume.to_numpy(),
        "adj_open": panel.adj_open.to_numpy(),
        "adj_close": panel.adj_close.to_numpy(),
    }


def last_row_index(panel: Panel) -> np.ndarray:
    present = panel.close.notna().to_numpy()
    idx = np.arange(len(panel.sessions))[:, None]
    return np.where(present, idx, -1).max(axis=0)


def run(panel: Panel, picks: dict[pd.Timestamp, list[str]], horizon: int,
        signal_start: str, signal_end: str, eligible: pd.DataFrame,
        avg_turnover: pd.DataFrame, settings: config.Settings,
        data_end: pd.Timestamp | None = None) -> Result:
    sessions = panel.sessions
    data_end = sessions[-1] if data_end is None else pd.Timestamp(data_end)
    last_data_idx = int(sessions.searchsorted(data_end, side="right") - 1)
    a = _arrays(panel)
    col_of = {code: i for i, code in enumerate(panel.close.columns)}
    last_idx = last_row_index(panel)
    turnover = avg_turnover.to_numpy()

    in_range = np.where((sessions >= pd.Timestamp(signal_start)) & (sessions <= pd.Timestamp(signal_end)))[0]
    # Keep only signals whose planned exit lies inside available data.
    in_range = in_range[in_range + horizon <= last_data_idx]
    if len(in_range) == 0:
        raise ValueError("no signal sessions in range")
    first_sig, last_sig = int(in_range[0]), int(in_range[-1])
    # The evaluation window ends at the last planned exit. Positions still stuck then
    # (long trading halts) are force-closed at their last mark and counted, so a period's
    # return series never runs on into later years.
    window_end = last_sig + horizon

    sleeves_cash = np.full(horizon, 1.0 / horizon)
    positions: list[Position] = []
    trades: list[dict] = []
    counters = {"signals": 0, "slots": 0, "filled": 0, "blocked_entry": 0,
                "delayed_exit": 0, "delisted_exit": 0, "forced_window_end_exit": 0}
    daily_rows = []
    prev_value = 1.0
    cm = 0.0 if settings.zero_cost else settings.cost_multiplier
    commission = config.COMMISSION * cm

    elig = eligible.to_numpy()
    adj_close = a["adj_close"]
    ret_cc = adj_close[1:] / adj_close[:-1] - 1  # ret_cc[d-1] = return on day d

    d = first_sig + 1
    while True:
        if d > last_data_idx:
            break
        date = sessions[d]
        tax = 0.0 if settings.zero_cost else config.sell_tax(date)
        # 1) Entries at today's open for yesterday's signal.
        sig = d - 1
        if first_sig <= sig <= last_sig:
            sleeve = (sig - first_sig) % horizon
            codes = picks.get(sessions[sig], [])
            counters["signals"] += 1
            slots = settings.top_n
            alloc = sleeves_cash[sleeve] / slots if slots else 0.0
            for code in codes:
                c = col_of[code]
                counters["slots"] += 1
                o, b, v = a["open"][d, c], a["base"][d, c], a["volume"][d, c]
                if not (v > 0 and o > 0 and b > 0) or o / b - 1 >= config.LIMIT_BAND:
                    counters["blocked_entry"] += 1
                    continue
                slip = config.slippage(turnover[sig, c]) * cm
                price = a["adj_open"][d, c] * (1 + slip) * (1 + commission)
                units = alloc / price
                sleeves_cash[sleeve] -= alloc
                positions.append(Position(sleeve, code, c, sessions[sig], d, sig + horizon, units,
                                          a["adj_open"][d, c], alloc, slip, alloc, int(last_idx[c])))
                counters["filled"] += 1
        # 2) Mark to market at today's close.
        for p in positions:
            px = adj_close[d, p.col]
            if np.isfinite(px):
                p.value = p.units * px
        # 3) Exits at today's close.
        keep = []
        for p in positions:
            exit_now, reason = False, "planned"
            if d >= p.planned_exit_idx:
                c, b = p.col, a["base"][d, p.col]
                traded = a["volume"][d, c] > 0 and np.isfinite(a["close"][d, c])
                locked = b > 0 and a["close"][d, c] / b - 1 <= -config.LIMIT_BAND
                if traded and not locked:
                    exit_now = True
                    reason = "planned" if d == p.planned_exit_idx else "delayed"
                elif d >= p.last_close_idx:
                    exit_now, reason = True, "delisted"
                elif d >= window_end:
                    exit_now, reason = True, "forced_window_end"
            elif d >= p.last_close_idx and p.last_close_idx < last_data_idx:
                exit_now, reason = True, "delisted"
            if not exit_now:
                keep.append(p)
                continue
            proceeds = p.value * (1 - p.slip) * (1 - commission - tax)
            sleeves_cash[p.sleeve] += proceeds
            if reason == "delayed":
                counters["delayed_exit"] += 1
            elif reason == "delisted":
                counters["delisted_exit"] += 1
            elif reason == "forced_window_end":
                counters["forced_window_end_exit"] += 1
            gross_exit_px = p.value / p.units
            trades.append({
                "signal_date": p.signal_date, "code": p.code, "entry_date": sessions[p.entry_idx],
                "exit_date": date, "sessions_held": d - p.entry_idx + 1, "exit_reason": reason,
                "gross_return": gross_exit_px / p.entry_adj_open - 1,
                "net_return": proceeds / p.cost_basis - 1,
            })
        positions = keep
        # 4) Account value and benchmark.
        value = float(sleeves_cash.sum() + sum(p.value for p in positions))
        invested = float(sum(p.value for p in positions)) / value if value > 0 else 0.0
        prior = elig[d - 1]
        r = ret_cc[d - 1][prior]
        r = r[np.isfinite(r)]
        bench = float(r.mean()) if len(r) else np.nan
        daily_rows.append({"date": date, "strategy": value / prev_value - 1,
                           "benchmark": bench, "invested": invested})
        prev_value = value
        if d >= window_end or (d > last_sig and not positions):
            break
        d += 1

    daily = pd.DataFrame(daily_rows).set_index("date")
    daily["excess"] = daily["strategy"] - daily["benchmark"]
    return Result(daily=daily, trades=pd.DataFrame(trades), counters=counters)
