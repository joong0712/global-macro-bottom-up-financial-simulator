"""Large indicator universe must be causal and correct on key reference formulas."""
import numpy as np
import pandas as pd
import pytest
from research.k_swing.indicators_expanded import compute_indicators, catalog_frame


def synthetic(n=410):
    d = pd.bdate_range("2022-01-03", periods=n)
    rng = np.random.default_rng(7162)
    base = np.exp(np.cumsum(rng.normal(.0003, .012, n))) * 10000
    op = base * (1 + rng.normal(0, .003, n))
    hi = np.maximum(op, base) * (1 + rng.uniform(.001, .02, n))
    lo = np.minimum(op, base) * (1 - rng.uniform(.001, .02, n))
    volume = rng.integers(100000, 1000000, n).astype(float)
    return pd.DataFrame({
        "open": op, "high": hi, "low": lo, "close": base,
        "volume": volume, "turnover": volume * base,
    }, index=d)


def test_catalog_breadth_and_expected_families():
    x = compute_indicators(synthetic())
    assert x.shape[1] >= 120
    assert not x.columns.duplicated().any()
    families = set(catalog_frame().family)
    assert {"trend", "ichimoku", "breakout", "momentum", "volume",
            "volatility", "support_resistance", "candlestick", "statistics"} <= families
    assert x.iloc[-1].notna().sum() >= 90


def test_ichimoku_current_cloud_is_shifted_from_past_only():
    p = synthetic()
    x = compute_indicators(p)
    tenkan = (p.high.rolling(9).max() + p.low.rolling(9).min()) / 2
    kijun = (p.high.rolling(26).max() + p.low.rolling(26).min()) / 2
    raw_a = (tenkan + kijun) / 2
    raw_b = (p.high.rolling(52).max() + p.low.rolling(52).min()) / 2
    cloud_a, cloud_b = raw_a.shift(26), raw_b.shift(26)
    date = p.index[-1]
    expected = p.loc[date, "close"] / max(cloud_a.loc[date], cloud_b.loc[date]) - 1
    assert x.loc[date, "ichi_cloud_top_gap"] == pytest.approx(expected)
    expected_projected = p.loc[date, "close"] / raw_a.loc[date] - 1
    assert x.loc[date, "ichi_span_a_projected_gap"] == pytest.approx(expected_projected)
    assert not any("chikou" in name.lower() for name in x.columns)


def test_future_data_mutation_cannot_change_past_values():
    p = synthetic()
    orig = compute_indicators(p)
    changed = p.copy()
    changed.loc[p.index[350]:, ["open", "high", "low", "close", "turnover"]] *= 1.6
    after = compute_indicators(changed)
    pd.testing.assert_frame_equal(orig.loc[:p.index[349]], after.loc[:p.index[349]])


def test_suspected_split_masks_long_lookbacks():
    p = synthetic()
    p["unsafe_session"] = False
    p.loc[p.index[240], "unsafe_session"] = True
    x = compute_indicators(p)
    assert x.loc[p.index[240]].isna().all()
    assert pd.isna(x.loc[p.index[280], "ichi_cloud_top_gap"])
    assert pd.isna(x.loc[p.index[280], "sma_gap_100"])
    assert pd.notna(x.loc[p.index[280], "candle_body_pct"])


def test_missing_session_does_not_invent_price():
    p = synthetic()
    p.loc[p.index[300], ["open", "high", "low", "close", "volume", "turnover"]] = np.nan
    x = compute_indicators(p)
    assert x.loc[p.index[300]].isna().all()
    assert pd.isna(x.loc[p.index[305], "sma_gap_20"])


def test_invalid_bar_order_rejected():
    with pytest.raises(ValueError, match="unique, sorted"):
        compute_indicators(synthetic().iloc[::-1])
