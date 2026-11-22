"""Synthetic checks: no future inputs, four frozen arms, identical history gate."""
import numpy as np
import pandas as pd
import pytest
from research.k_swing.alpha_candidates_v11 import symbol_candidates, build_candidates, METHODS


def bars_template():
    dates = pd.bdate_range("2019-01-01", periods=325)
    close = np.full(len(dates), 100., dtype=float)
    x = pd.DataFrame({"date": dates, "ticker": "000001",
                      "open": close.copy(), "high": close + .5,
                      "low": close - .5, "close": close.copy(),
                      "volume": np.full(len(dates), 1e6),
                      "turnover": np.full(len(dates), 4e9),
                      "unsafe_session": False})
    return dates, x


def candle(df, idx, price, volume=2e6):
    df.loc[idx, ["open", "high", "low", "close", "volume"]] = [
        price, price + .5, price - .5, price, volume]


def test_52_week_price_momentum():
    d, x = bars_template()
    candle(x, x.index[-1], 120.)
    result = symbol_candidates(x, d)
    assert result.strategy.eq("momentum52").any()
    assert not result.strategy.eq("reversal3").any()


def test_reversal_after_uptrend_dip():
    d, x = bars_template()
    for col, value in (("open", 115.), ("high", 115.5),
                       ("low", 114.5), ("close", 115.)):
        x.loc[x.index[-50:-1], col] = value
    candle(x, x.index[-1], 106.)
    result = symbol_candidates(x, d)
    assert result.strategy.eq("reversal3").any()
    assert not result.strategy.eq("momentum52").any()


def test_vcr_trend_and_control_on_compressed_breakout():
    d, x = bars_template()
    prices = np.full(len(d), 100.)
    prices[:50] = 100 + np.sin(np.arange(50) / 2) * 10
    x["open"] = prices
    x["high"] = prices + .5
    x["low"] = prices - .5
    x["close"] = prices
    candle(x, x.index[-1], 112.)
    result = symbol_candidates(x, d)
    for name in ("vcr_trend", "vcr_control"):
        assert result.strategy.eq(name).any()


def test_unsafe_event_and_calendar_gap_in_253_session_history():
    d, x = bars_template()
    candle(x, x.index[-1], 120.)
    assert symbol_candidates(x, d).strategy.eq("momentum52").any()
    x.loc[x.index[-253], "unsafe_session"] = True
    assert symbol_candidates(x, d).empty
    d, x = bars_template()
    candle(x, x.index[-1], 120.)
    x = x.loc[x.date.ne(d[-230])]
    assert symbol_candidates(x, d).empty


def test_future_cannot_change_previous_signal():
    d, x = bars_template()
    candle(x, x.index[-2], 120.)
    earlier = symbol_candidates(x, d)
    x2 = x.copy()
    candle(x2, x2.index[-1], 160.)
    later = symbol_candidates(x2, d)
    a = earlier[earlier.date.eq(d[-2])].sort_values("strategy").reset_index(drop=True)
    b = later[later.date.eq(d[-2])].sort_values("strategy").reset_index(drop=True)
    pd.testing.assert_frame_equal(a, b)


def test_locked_2023_and_late_first_signal():
    d, x = bars_template()
    future = pd.bdate_range("2023-01-02", periods=len(d))
    with pytest.raises(ValueError, match="locked"):
        symbol_candidates(x.assign(date=future), future)
    with pytest.raises(ValueError, match="locked"):
        build_candidates(x, d, first_signal="2026-01-01")


def test_only_four_preregistered_methods():
    assert METHODS == ("momentum52", "reversal3", "vcr_trend", "vcr_control")
