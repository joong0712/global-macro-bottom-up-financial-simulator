"""Tests for precisely matched trade opportunities, stop-first and uncertainty."""
import numpy as np
import pandas as pd
import pytest

from research.k_swing.paired_exit_v15 import (
    COST_BPS, TradeOutcome, after_cost, paired_block_ci,
    evaluate_matched_trade, paired_comparison,
)
from research.k_swing.ichimoku_ma_exit_v14 import simulate_exit_policy


def fixture():
    dates = pd.bdate_range("2019-01-02", periods=355)
    p = np.full(len(dates), 2000., dtype=float)
    bars = pd.DataFrame({
        "date": dates, "ticker": "000456",
        "open": p, "high": p + 45, "low": p - 45,
        "close": p, "volume": 1e6, "turnover": 5e9,
        "unsafe_session": False,
    })
    signals = pd.DataFrame({
        "date": [dates[310]], "ticker": ["000456"],
        "score": [-.8], "turnover": [5e9],
    })
    return dates, bars, signals


def test_isolated_baseline_matches_cash_book_for_single_signal():
    dates, bars, signals = fixture()
    for horizon in (5, 10):
        event = evaluate_matched_trade(
            bars, dates, signals.date.iloc[0], horizon=horizon,
            mode="baseline")
        assert event is not None
        assert event.cause == "time_close"
        cash = simulate_exit_policy(
            bars, signals, dates, exit_mode="baseline", horizon=horizon)
        # Roundtrip fractional return of an integer-share ticket vs full
        # fractional theoretical trade differs only by ticket rounding.
        account_return = cash["hypothetical_net_return_if_resolved"]
        assert account_return == pytest.approx(
            after_cost(event, 50) * (cash["realized_buy_notional_krw"]
                                     * 1.0025 / 100_000_000), abs=1e-10)


def test_next_open_indicator_is_not_same_day_close_or_future_high():
    dates, bars, signals = fixture()
    t = 310
    bars.loc[t + 1, ["open", "high", "low", "close"]] = [
        2000., 2040., 1960., 1970.]
    bars.loc[t + 2, ["open", "high", "low", "close"]] = [
        2020., 2050., 1980., 2000.]
    from research.k_swing.ichimoku_ma_exit_v14 import exit_flags
    flags = exit_flags(bars, dates, "kijun_break")
    outcome = evaluate_matched_trade(
        bars, dates, dates[t], horizon=5, mode="kijun_break",
        instructions=flags)
    assert outcome.cause == "next_open_indicator_exit"
    assert outcome.exit == pytest.approx(2020.)
    assert outcome.sessions_held == 2
    report = paired_comparison(
        bars, signals, dates, first=dates[290], last=dates[325], horizon=5)
    x = report["comparisons"][0]["cost_50bps"]
    assert report["completed_matched"] == 1
    assert x["mean_matched_improvement"] > 0


def test_stop_first_overrides_next_day_indicator_decision():
    dates, bars, signals = fixture()
    t = 310
    bars.loc[t + 1, ["open", "high", "low", "close"]] = [
        2000., 2200., 1870., 1900.]
    trade = evaluate_matched_trade(
        bars, dates, dates[t], horizon=5, mode="either_break")
    assert trade.cause == "intraday_stop_first"
    assert trade.exit == pytest.approx(1940.)
    assert trade.sessions_held == 1


def test_any_unsafe_held_session_blocks_entire_cohort_no_cherry_picking():
    dates, bars, signals = fixture()
    bars.loc[312, "unsafe_session"] = True
    report = paired_comparison(
        bars, signals, dates, first=dates[290], last=dates[325], horizon=5)
    assert report["status"] == "BLOCKED_UNVERIFIED_HELD_BAR"
    assert report["comparisons"] == []
    assert report["completed_matched"] is None


def test_known_missing_entry_skips_without_imputing_trade_return():
    dates, bars, signals = fixture()
    bars.loc[311, "unsafe_session"] = True
    report = paired_comparison(
        bars, signals, dates, first=dates[290], last=dates[325], horizon=5)
    assert report["status"] == "NO_MATCHED_TRADES"
    assert report["completed_matched"] == 0


def test_cost_sensitivity_and_bootstrap_are_deterministic():
    t = TradeOutcome(entry=100., exit=101., sessions_held=3, cause="time_close")
    assert COST_BPS == (50, 100, 200)
    assert after_cost(t, 50) > after_cost(t, 100) > after_cost(t, 200)
    values = np.array([.002, -.001, .004, .002, -.002, .01])
    positions = np.array([5, 6, 30, 32, 70, 71])
    a = paired_block_ci(values, positions, 100, seed=7)
    b = paired_block_ci(values, positions, 100, seed=7)
    assert a == b
    assert a[0] <= a[1]
    zero = paired_block_ci(np.zeros(6), positions, 100)
    assert zero == (0.0, 0.0)


def test_no_2023_period_or_unapproved_exit():
    dates, bars, signals = fixture()
    with pytest.raises(ValueError, match="Only reused historical"):
        paired_comparison(bars, signals, dates,
                          first=pd.Timestamp("2023-01-01"),
                          last=pd.Timestamp("2024-01-01"), horizon=5)
    with pytest.raises(ValueError, match="Frozen"):
        evaluate_matched_trade(bars, dates, dates[310],
                               horizon=5, mode="oracle")
