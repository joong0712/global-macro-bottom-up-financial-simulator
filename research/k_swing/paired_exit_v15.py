"""Matched opportunity comparison for Korean swing early exits.

One T-close candidate -> one T+1 opening-print purchase; every exit
policy is evaluated on the SAME ticker and entry price, outside the
cash-portfolio engine. This isolates exit-rule effects but DOES NOT
establish a tradable capital-constrained portfolio.

Stock/date/individual-trade data never leave the private CI runner.
"""
from __future__ import annotations

from dataclasses import dataclass
import numpy as np
import pandas as pd

from .ichimoku_ma_exit_v14 import EXIT_MODES, exit_flags
from .vcr_strategy_v10 import _calendar

COST_BPS = (50, 100, 200)
BLOCK_SESSIONS = 20
N_BOOT = 2000


@dataclass(frozen=True)
class TradeOutcome:
    entry: float
    exit: float
    sessions_held: int
    cause: str


def _valid_bar(record):
    if record is None or pd.isna(record.unsafe_session) or bool(record.unsafe_session):
        return False
    prices = tuple(float(getattr(record, field))
                   for field in ("open", "high", "low", "close"))
    if not all(np.isfinite(x) and x > 0 for x in prices):
        return False
    op, hi, lo, cl = prices
    return lo <= min(op, cl) <= max(op, cl) <= hi


def evaluate_matched_trade(
    stock: pd.DataFrame, calendar: pd.DatetimeIndex, signal_day: pd.Timestamp,
    *, horizon: int, mode: str,
    instructions: set[tuple[pd.Timestamp, str]] | None = None,
) -> TradeOutcome | None:
    """Conservatively return None for any unresolved *held* price event.

    T signal -> T+1 open. Stop/take intraday priority is identical to v1.4.
    A breach seen at held-day close triggers next day's OPEN exit only.
    Never uses next day's close to choose an action.
    """
    dates = _calendar(calendar)
    if mode not in EXIT_MODES or horizon not in (5, 10):
        raise ValueError("Frozen exit method and horizons only")
    if not {"date", "ticker", "open", "high", "low", "close", "unsafe_session"}.issubset(stock):
        raise ValueError("Unscreened historical stock bars")
    if stock.empty or stock.ticker.nunique() != 1:
        raise ValueError("One ticker per paired study")
    code = str(stock.ticker.iloc[0])
    when = pd.Timestamp(signal_day).normalize()
    rank = dates.get_indexer([when])[0]
    if rank < 0 or rank + horizon >= len(dates):
        return None
    x = stock.copy()
    x.date = pd.to_datetime(x.date).dt.normalize()
    if x.date.duplicated().any() or not x.date.isin(dates).all():
        raise ValueError("Unordered/duplicate/out-of-calendar price bars")
    rows = {r.date: r for r in x.itertuples(index=False)}
    first_bar = rows.get(dates[rank + 1])
    if not _valid_bar(first_bar):
        return None
    entry = float(first_bar.open)
    stop, take = entry * .97, entry * 1.08
    ins = instructions if instructions is not None else set()
    next_open_exit = False
    for k in range(1, horizon + 1):
        day = dates[rank + k]
        bar = rows.get(day)
        if not _valid_bar(bar):
            return None
        if next_open_exit:
            return TradeOutcome(entry, float(bar.open), k, "next_open_indicator_exit")
        if bar.open <= stop:
            return TradeOutcome(entry, float(bar.open), k, "gap_stop")
        if bar.open >= take:
            return TradeOutcome(entry, float(bar.open), k, "gap_take")
        if bar.low <= stop:
            return TradeOutcome(entry, stop, k, "intraday_stop_first")
        if bar.high >= take:
            return TradeOutcome(entry, take, k, "intraday_take")
        if k == horizon:
            return TradeOutcome(entry, float(bar.close), k, "time_close")
        next_open_exit = (day, code) in ins
    raise AssertionError("Every known safe held position must resolve by horizon")


def after_cost(outcome: TradeOutcome, roundtrip_bps: int) -> float:
    if roundtrip_bps not in COST_BPS:
        raise ValueError("Only predeclared cost stresses allowed")
    half = roundtrip_bps / 20000.
    return outcome.exit / outcome.entry * (1 - half) / (1 + half) - 1


def paired_block_ci(
    deltas: np.ndarray, positions: np.ndarray, n_calendar_sessions: int,
    *, seed: int = 1024, boots: int = N_BOOT,
) -> tuple[float | None, float | None]:
    """20-market-session nonoverlapping calendar-block bootstrap on matched trades.

    Calendar blocks (not trades) are resampled with replacement, retaining
    within-block stock correlation. CI is a diagnostic, not a multiple-
    comparisons corrected p-value, and isn't an untouched OOS test.
    """
    delta = np.asarray(deltas, dtype=float)
    pos = np.asarray(positions, dtype=int)
    if (len(delta) == 0 or len(delta) != len(pos)
            or n_calendar_sessions <= 0 or boots < 100
            or not np.isfinite(delta).all() or (pos < 0).any()
            or (pos >= n_calendar_sessions).any()):
        raise ValueError("Invalid block-bootstrap inputs")
    group_id = pos // BLOCK_SESSIONS
    n_blocks = (n_calendar_sessions + BLOCK_SESSIONS - 1) // BLOCK_SESSIONS
    sums = np.bincount(group_id, weights=delta, minlength=n_blocks)
    counts = np.bincount(group_id, minlength=n_blocks)
    rng = np.random.default_rng(seed)
    draws = rng.integers(0, n_blocks, size=(boots, n_blocks))
    sampled_count = counts[draws].sum(axis=1)
    valid = sampled_count > 0
    if valid.sum() < boots * .9:
        return None, None
    means = sums[draws[valid]].sum(axis=1) / sampled_count[valid]
    low, high = np.quantile(means, [.025, .975])
    return float(low), float(high)


def paired_comparison(
    bars: pd.DataFrame, signals: pd.DataFrame, calendar: pd.DatetimeIndex,
    *, first: pd.Timestamp, last: pd.Timestamp, horizon: int,
    seed: int = 1234,
) -> dict:
    """Compare fixed exits with matched entry tickets and aggregate diagnostics.

    Even one unresolved held security event blocks the WHOLE comparison.
    Suspect outcomes are never dropped to make a rule look profitable.
    """
    dates = _calendar(calendar)
    first, last = pd.Timestamp(first), pd.Timestamp(last)
    if first < pd.Timestamp("2019-01-01") or last > pd.Timestamp("2022-12-15"):
        raise ValueError("Only reused historical discovery/development windows")
    if first >= last or horizon not in (5, 10):
        raise ValueError("Invalid paired scenario")
    required = {"date", "ticker", "score", "turnover"}
    if not required.issubset(signals):
        raise ValueError("Signals missing required source fields")
    s = signals.copy()
    s.date = pd.to_datetime(s.date).dt.normalize()
    if s.duplicated(["date", "ticker"]).any() or not s.date.isin(dates).all():
        raise ValueError("Missing unique as-of stock/date")
    s = s.loc[s.date.between(first, last)].copy()
    if s.empty:
        return {"status": "NO_SIGNALS", "n_signals": 0, "completed_matched": 0,
                "comparisons": []}
    # Apply same eligibility/ranking as existing portfolio engine: top 10
    # per date; no future information affects opportunity selection.
    if s[["score", "turnover"]].isna().any().any():
        raise ValueError("Missing as-of score or turnover")
    s = s.loc[s.turnover.ge(1e9)].sort_values(
        ["date", "score", "ticker"], kind="stable"
    ).groupby("date", group_keys=False).head(10)
    groups = {str(ticker): group for ticker, group in bars.groupby("ticker")}
    flags = {mode: exit_flags(bars, dates, mode) for mode in EXIT_MODES}
    stock_rows = {}
    matrix = []
    unverified = 0
    missing_entries = 0
    ix = {day: idx for idx, day in enumerate(dates)}
    start_pos = ix[dates[dates.searchsorted(first)]]
    end_pos = ix[dates[dates.searchsorted(last, side="right") - 1]]
    for row in s.itertuples(index=False):
        ticker, signal_date = str(row.ticker), pd.Timestamp(row.date)
        i = ix[signal_date]
        if i + horizon >= len(dates):
            continue
        if ticker not in groups:
            raise ValueError("Selected stock missing in historical bars")
        # Missing/unsafe ENTRY never opens a trade in the original engine.
        raw = groups[ticker].set_index("date").reindex(dates)
        entry = raw.iloc[i + 1]
        if (pd.isna(entry.unsafe_session) or bool(entry.unsafe_session)
                or not np.isfinite(float(entry.open)) or entry.open <= 0):
            missing_entries += 1
            continue
        out = {}
        for mode in EXIT_MODES:
            trade = evaluate_matched_trade(
                groups[ticker], dates, signal_date, horizon=horizon,
                mode=mode, instructions=flags[mode],
            )
            if trade is None:
                unverified += 1
                out = None
                break
            out[mode] = trade
        if out is None:
            continue
        matrix.append((i - start_pos, out))
    if unverified:
        return {"status": "BLOCKED_UNVERIFIED_HELD_BAR",
                "n_signals": int(len(s)),
                "skipped_missing_entry": missing_entries,
                "unverified_trade_encounters": unverified,
                "completed_matched": None,
                "comparisons": []}
    if not matrix:
        return {"status": "NO_MATCHED_TRADES", "n_signals": int(len(s)),
                "completed_matched": 0, "comparisons": []}
    positions = np.array([pair[0] for pair in matrix], dtype=int)
    if (positions < 0).any() or (positions > end_pos - start_pos).any():
        raise AssertionError("An evaluation signal is outside the predeclared period")
    outcomes = {mode: [pair[1][mode] for pair in matrix]
                for mode in EXIT_MODES}
    comparisons = []
    for mode in EXIT_MODES[1:]:
        item = {"compared_exit": mode, "matched_trades": len(matrix)}
        for cost in COST_BPS:
            base = np.array([after_cost(t, cost) for t in outcomes["baseline"]])
            variant = np.array([after_cost(t, cost) for t in outcomes[mode]])
            delta = variant - base
            low, high = paired_block_ci(
                delta, positions, end_pos - start_pos + 1,
                seed=seed + 19 * cost + 100 * horizon + EXIT_MODES.index(mode),
            )
            item[f"cost_{cost}bps"] = {
                "baseline_mean_net_trade": float(base.mean()),
                "variant_mean_net_trade": float(variant.mean()),
                "mean_matched_improvement": float(delta.mean()),
                "paired_20session_block_ci95_lower": low,
                "paired_20session_block_ci95_upper": high,
                "win_fraction": float((variant > 0).mean()),
                "mean_holding_sessions": float(np.mean(
                    [x.sessions_held for x in outcomes[mode]])),
                "diagnostic_positive_net_and_ci_at_50bps": bool(
                    cost == 50 and len(matrix) >= 30
                    and variant.mean() > 0 and low is not None and low > 0
                ),
            }
        comparisons.append(item)
    return {
        "status": "PAIRED_TRADE_DIAGNOSTIC_NOT_CAPITAL_PORTFOLIO",
        "n_signals": int(len(s)),
        "completed_matched": len(matrix),
        "skipped_missing_entry": missing_entries,
        "unverified_trade_encounters": unverified,
        "bootstrap_calendar_block_sessions": BLOCK_SESSIONS,
        "bootstrap_resamples": N_BOOT,
        "comparisons": comparisons,
    }
