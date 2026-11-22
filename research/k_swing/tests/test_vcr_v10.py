"""No-lookahead signals, conservative bracket path and locked confirmation data."""
import numpy as np
import pandas as pd
import pytest

from research.k_swing.vcr_strategy_v10 import VCRConfig, symbol_signal_flags, build_signals
from research.k_swing.vcr_execution_v10 import simulate_brackets


def fixture():
    dates = pd.bdate_range("2020-01-01", periods=205)
    # First 50 days volatile, followed by long compression and 20-day flat high.
    prices = np.full(len(dates), 100.)
    prices[:50] = 100 + np.sin(np.arange(50) / 2) * 10
    prices[-1] = 110.
    frame = pd.DataFrame({"date": dates, "ticker": "000001",
                          "open": prices, "high": prices + .5,
                          "low": prices - .5, "close": prices,
                          "volume": np.full(len(dates), 1_000_000.),
                          "turnover": np.full(len(dates), 4e9),
                          "unsafe_session": False})
    frame.loc[frame.index[-1], "volume"] = 2_000_000
    return dates, frame


def test_vcr_breakout_is_past_only_and_all_baselines_trigger():
    dates, df = fixture()
    sig = symbol_signal_flags(df, dates)
    at = sig.iloc[-1]
    assert at.breakout and at.breakout_volume and at.vcr
    assert at.score < 0
    earlier = sig.iloc[-2]
    assert not earlier.vcr
    # Editing a later observation cannot change already-sent T-close signals.
    other = df.copy()
    other.loc[other.index[-1], ["close", "high", "volume"]] = [150, 151, 5e6]
    assert symbol_signal_flags(other, dates).iloc[-2]["score"] == earlier.score


def test_breakout_day_width_is_never_required_to_remain_compressed():
    dates, df = fixture()
    # Very large breakout widens current Bollinger width, but yesterday was flat.
    df.loc[df.index[-1], ["open", "high", "low", "close"]] = [150., 151., 149., 150.]
    assert symbol_signal_flags(df, dates).iloc[-1].vcr


def test_unsafe_or_missing_history_blocks_signal():
    dates, df = fixture()
    df.loc[df.index[-22], "unsafe_session"] = True
    assert not symbol_signal_flags(df, dates).iloc[-1].vcr
    dates, df = fixture()
    df = df.loc[df.date.ne(dates[-15])]
    assert not symbol_signal_flags(df, dates).iloc[-1].vcr


def test_volume_ratio_and_turnover_filters():
    dates, df = fixture()
    df.loc[df.index[-1], "volume"] = 1_700_000
    out = symbol_signal_flags(df, dates).iloc[-1]
    assert out.breakout and not out.breakout_volume and not out.vcr
    dates, df = fixture()
    df.loc[df.index[-1], "turnover"] = 1e8
    assert not symbol_signal_flags(df, dates).iloc[-1].breakout


def test_all_signal_dates_require_training_only():
    dates, df = fixture()
    flags = build_signals(df, dates)
    assert set(flags.strategy) == {"breakout", "breakout_volume", "vcr"}
    future = pd.bdate_range("2023-01-02", periods=205)
    with pytest.raises(ValueError, match="locked"):
        symbol_signal_flags(df.assign(date=future), future)
    with pytest.raises(ValueError, match="locked"):
        build_signals(df, dates, first_signal="2026-01-01")


def engine_inputs():
    d = pd.bdate_range("2022-01-03", periods=15)
    x = pd.DataFrame({"date": d, "ticker": "000001", "open": 100.,
                      "high": 101., "low": 99., "close": 100.,
                      "unsafe_session": False})
    s = pd.DataFrame({"date": [d[0]], "ticker": ["000001"],
                      "score": [-0.1], "turnover": [3e9]})
    return d, x, s


def test_both_hit_stop_first_and_gap_stops_at_open():
    d, x, s = engine_inputs()
    x.loc[x.date.eq(d[1]), ["high", "low"]] = [110., 90.]
    r = simulate_brackets(x, s, d, horizon=5,
                          initial_cash_krw=10000, ticket_krw=1000,
                          assumed_roundtrip_bps=0)
    assert r["exit_causes"] == {"intraday_stop_first": 1}
    assert r["hypothetical_net_return_if_resolved"] == pytest.approx(-.003)
    d, x, s = engine_inputs()
    x.loc[x.date.eq(d[1]), ["open", "high", "low", "close"]] = [90., 101., 89., 100.]
    r = simulate_brackets(x, s, d, horizon=5,
                          initial_cash_krw=10000, ticket_krw=1000,
                          assumed_roundtrip_bps=0)
    # Gap on entry day sets entry at 90, so no stop relative to previous close 100.
    assert r["completed_trades"] == 1
    assert r["exit_causes"] == {"intraday_take": 1}


def test_gap_after_entry_exits_at_open_not_hypothetical_stop():
    d, x, s = engine_inputs()
    x.loc[x.date.eq(d[2]), ["open", "low", "high", "close"]] = [85., 84., 100., 90.]
    r = simulate_brackets(x, s, d, horizon=5,
                          initial_cash_krw=10000, ticket_krw=1000,
                          assumed_roundtrip_bps=0)
    assert r["exit_causes"] == {"gap_stop": 1}
    assert r["hypothetical_net_return_if_resolved"] == pytest.approx(-.015)


def test_unverified_holding_bar_blocks_every_pnl_claim():
    d, x, s = engine_inputs()
    x.loc[x.date.eq(d[3]), "unsafe_session"] = True
    r = simulate_brackets(x, s, d, horizon=5,
                          initial_cash_krw=10000, ticket_krw=1000)
    assert r["status"].startswith("BLOCKED")
    assert r["hypothetical_net_return_if_resolved"] is None
    assert r["hypothetical_marked_mdd_if_resolved"] is None


def test_fixed_exit_at_t_plus_h_and_missing_next_open_not_substituted():
    d, x, s = engine_inputs()
    r = simulate_brackets(x, s, d, horizon=5,
                          initial_cash_krw=10000, ticket_krw=1000,
                          assumed_roundtrip_bps=0)
    assert r["exit_causes"] == {"time_close": 1}
    x.loc[x.date.eq(d[1]), "open"] = np.nan
    r = simulate_brackets(x, s, d, horizon=5)
    assert r["completed_trades"] == 0
    assert r["skip_reasons"]["no_next_open_print"] == 1
