"""Synthetic causal entry timing tests: visible Ichimoku and next-open fills."""
import numpy as np
import pandas as pd
import pytest

from research.k_swing.ichimoku_ma_timing_v13 import (
    METHODS, indicator_frame, symbol_timing_candidates,
)
from research.k_swing.vcr_execution_v10 import simulate_brackets


def fixture():
    dates = pd.bdate_range("2019-01-02", periods=335)
    p = np.full(len(dates), 2000.)
    b = pd.DataFrame({
        "date": dates, "ticker": "000333",
        "open": p, "high": p + 10, "low": p - 10, "close": p,
        "volume": 1e6, "turnover": 4e9, "unsafe_session": False,
    })
    # An older low inside Kijun's 26 but outside Tenkan's 9 sessions.
    b.loc[b.index[-15], "low"] = 1500.
    b.loc[b.index[-1], ["open", "high", "low", "close", "volume"]] = [
        2250., 2260., 2240., 2250., 2e6]
    return dates, b


def test_cloud_uses_26_day_old_data_not_future():
    dates, bars = fixture()
    ind = indicator_frame(bars, dates)
    h = bars.high
    lo = bars.low
    tenkan = (h.rolling(9, min_periods=9).max()
              + lo.rolling(9, min_periods=9).min()) / 2
    kijun = (h.rolling(26, min_periods=26).max()
             + lo.rolling(26, min_periods=26).min()) / 2
    span_b = (h.rolling(52, min_periods=52).max()
              + lo.rolling(52, min_periods=52).min()) / 2
    i = len(bars) - 1
    assert ind.cloud_a.iloc[i] == pytest.approx(
        (tenkan.iloc[i - 26] + kijun.iloc[i - 26]) / 2)
    assert ind.cloud_b.iloc[i] == pytest.approx(span_b.iloc[i - 26])
    earlier = ind.iloc[-2].copy()
    changed = bars.copy()
    changed.loc[changed.index[-1], ["open", "high", "low", "close"]] = [
        2500., 2510., 2490., 2500.]
    pd.testing.assert_series_equal(
        earlier, indicator_frame(changed, dates).iloc[-2])


def test_five_predeclared_entry_methods_fire_on_valid_fixture():
    dates, b = fixture()
    out = symbol_timing_candidates(b, dates)
    last = set(out.loc[out.date.eq(dates[-1])].strategy)
    assert {"ichi_cloud_breakout", "ma_5x20", "ma20_reclaim",
            "ichi_ma_confirm"}.issubset(last)
    # Distinct Kijun reclaim: prior close <= Kijun and new close above.
    b.loc[b.index[-2], ["open", "high", "low", "close"]] = [
        1800., 2010., 1690., 1700.]
    out = symbol_timing_candidates(b, dates)
    assert "ichi_kijun_reclaim" in set(out.loc[out.date.eq(dates[-1])].strategy)


def test_full_253_history_and_locked_2023():
    d, b = fixture()
    assert not symbol_timing_candidates(b, d).empty
    b.loc[b.index[-253], "unsafe_session"] = True
    out = symbol_timing_candidates(b, d)
    assert not out.date.eq(d[-1]).any()
    d2 = pd.bdate_range("2023-01-02", periods=len(d))
    with pytest.raises(ValueError, match="locked"):
        indicator_frame(b.assign(date=d2), d2)


def test_next_vs_second_open_uses_different_known_entry_price():
    d = pd.bdate_range("2019-01-01", periods=35)
    b = pd.DataFrame({
        "date": d, "ticker": "000333",
        "open": 2000., "high": 2050., "low": 1980., "close": 2000.,
        "volume": 1e6, "turnover": 4e9, "unsafe_session": False,
    })
    t = 15
    # T+2 opens at a known higher historical print; no filters on T+1 path.
    b.loc[t + 2, ["open", "high", "low", "close"]] = [
        2040., 2060., 1990., 2030.]
    sig = pd.DataFrame({"date": [d[t]], "ticker": ["000333"],
                        "score": [-1.], "turnover": [4e9]})
    r1 = simulate_brackets(b, sig, d, horizon=5, entry_delay_sessions=1)
    r2 = simulate_brackets(b, sig, d, horizon=5, entry_delay_sessions=2)
    assert r1["status"] == r2["status"] == "HYPOTHETICAL_OHLC_ONLY"
    assert r1["completed_trades"] == r2["completed_trades"] == 1
    assert r1["entry_delay_sessions"] == 1
    assert r2["entry_delay_sessions"] == 2
    assert r1["hypothetical_net_return_if_resolved"] > r2["hypothetical_net_return_if_resolved"]
    with pytest.raises(ValueError, match="Invalid"):
        simulate_brackets(b, sig, d, horizon=5, entry_delay_sessions=0)


def test_list_is_frozen_before_evaluation():
    assert METHODS == (
        "ichi_cloud_breakout", "ichi_kijun_reclaim", "ma_5x20",
        "ma20_reclaim", "ichi_ma_confirm", "vcr_trend_control",
    )
