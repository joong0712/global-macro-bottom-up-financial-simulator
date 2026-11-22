"""No-future early exit and baseline-parity tests, fully synthetic OHLCV."""
import numpy as np
import pandas as pd
import pytest

from research.k_swing.ichimoku_ma_exit_v14 import (
    EXIT_MODES, exit_flags, simulate_exit_policy,
)
from research.k_swing.vcr_execution_v10 import simulate_brackets


def bars_fixture():
    d = pd.bdate_range("2019-01-02", periods=355)
    p = np.full(len(d), 2000., dtype=float)
    bars = pd.DataFrame({
        "date": d, "ticker": "000456",
        "open": p, "high": p + 50, "low": p - 50, "close": p,
        "volume": 1e6, "turnover": 5e9, "unsafe_session": False,
    })
    return d, bars


def signal_at(d, i=310):
    return pd.DataFrame({
        "date": [d[i]], "ticker": ["000456"],
        "score": [-.8], "turnover": [5e9],
    })


@pytest.mark.parametrize("hold", [5, 10])
def test_baseline_matches_unchanged_v13_execution(hold):
    d, b = bars_fixture()
    s = signal_at(d)
    old = simulate_brackets(b, s, d, horizon=hold)
    new = simulate_exit_policy(b, s, d, exit_mode="baseline", horizon=hold)
    assert old["status"] == new["status"] == "HYPOTHETICAL_OHLC_ONLY"
    assert old["completed_trades"] == new["completed_trades"] == 1
    assert old["hypothetical_net_return_if_resolved"] == pytest.approx(
        new["hypothetical_net_return_if_resolved"], abs=1e-13)
    assert old["hypothetical_marked_mdd_if_resolved"] == pytest.approx(
        new["hypothetical_marked_mdd_if_resolved"], abs=1e-13)
    assert new["mean_daily_invested_fraction_if_resolved"] > 0


def test_close_signal_exits_no_earlier_than_next_open():
    d, b = bars_fixture()
    t = 310
    # Holding starts at open T+1=2000. Low T+1=1960 is above 1940 stop.
    b.loc[t+1, ["open", "high", "low", "close"]] = [
        2000., 2040., 1960., 1970.]
    # Next open is 2020, distinct from T+1 close 1970.
    b.loc[t+2, ["open", "high", "low", "close"]] = [
        2020., 2050., 1980., 2000.]
    s = signal_at(d, t)
    base = simulate_exit_policy(b, s, d, exit_mode="baseline")
    early = simulate_exit_policy(b, s, d, exit_mode="kijun_break")
    assert early["completed_trades"] == 1
    assert early["exit_causes"] == {"next_open_indicator_exit": 1}
    assert base["exit_causes"] == {"time_close": 1}
    assert early["hypothetical_net_return_if_resolved"] > (
        base["hypothetical_net_return_if_resolved"])


def test_stop_remains_first_even_if_close_breaches_kijun():
    d, b = bars_fixture()
    t = 310
    b.loc[t+1, ["open", "high", "low", "close"]] = [
        2000., 2040., 1880., 1900.]
    result = simulate_exit_policy(b, signal_at(d, t), d,
                                  exit_mode="either_break")
    assert result["exit_causes"]["intraday_stop_first"] == 1
    assert result["exit_causes"].get("next_open_indicator_exit", 0) == 0


def test_unsafe_bar_blocks_all_return_claim():
    d, b = bars_fixture()
    t = 310
    b.loc[t+1, "unsafe_session"] = True
    result = simulate_exit_policy(b, signal_at(d, t), d,
                                  exit_mode="baseline")
    # No purchase possible on unsafe entry print; no traded PnL.
    assert result["completed_trades"] == 0
    d, b = bars_fixture()
    b.loc[t+2, "unsafe_session"] = True
    result = simulate_exit_policy(b, signal_at(d, t), d,
                                  exit_mode="baseline")
    assert result["status"] == "BLOCKED_UNRESOLVED_POSITION"
    assert result["hypothetical_net_return_if_resolved"] is None


def test_exposure_window_excludes_warmup_cash_but_does_not_change_return():
    d, b = bars_fixture()
    signals = signal_at(d)
    all_dates = simulate_exit_policy(b, signals, d, exit_mode="baseline", horizon=5)
    within = simulate_exit_policy(
        b, signals, d, exit_mode="baseline", horizon=5,
        exposure_window_start=d[300], exposure_window_end=d[320])
    assert within["hypothetical_net_return_if_resolved"] == pytest.approx(
        all_dates["hypothetical_net_return_if_resolved"])
    assert within["mean_daily_invested_fraction_if_resolved"] > (
        all_dates["mean_daily_invested_fraction_if_resolved"])
    assert within["exposure_window_start"] == str(d[300].date())
    with pytest.raises(ValueError, match="Both"):
        simulate_exit_policy(
            b, signals, d, exit_mode="baseline", horizon=5,
            exposure_window_start=d[300])


def test_tomorrows_candle_never_changes_yesterdays_exit_signal():
    d, b = bars_fixture()
    b.loc[b.index[-2], ["open", "high", "low", "close"]] = [
        2000., 2040., 1930., 1960.]
    before = {pair for pair in exit_flags(b, d, "either_break")
              if pair[0] < d[-1]}
    modified = b.copy()
    modified.loc[modified.index[-1], ["open", "high", "low", "close"]] = [
        2350., 2400., 2320., 2360.]
    after = {pair for pair in exit_flags(modified, d, "either_break")
             if pair[0] < d[-1]}
    assert before == after


def test_locked_dates_and_frozen_strategies():
    d, b = bars_fixture()
    assert EXIT_MODES == ("baseline", "kijun_break", "sma20_break", "either_break")
    with pytest.raises(ValueError, match="locked"):
        future = pd.bdate_range("2023-01-02", periods=len(d))
        exit_flags(b.assign(date=future), future, "kijun_break")
    with pytest.raises(ValueError, match="Unknown"):
        exit_flags(b, d, "future_oracle")
