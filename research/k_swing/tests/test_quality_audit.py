"""Structural quality screening checks. Synthetic input only, no exchange access."""
import numpy as np
import pandas as pd
import pytest
from research.k_swing.quality_audit import compare_calendars, marcap_metadata, screen_year
from research.k_swing.data import validate_prices
from research.k_swing.factors import compute_symbol_factors
from research.k_swing.targets import make_symbol_targets


def example():
    dates = pd.bdate_range("2024-01-02", periods=40)
    p = pd.DataFrame({
        "date": dates, "ticker": ["000001"] * 40,
        "open": 100., "high": 101., "low": 99., "close": 100.,
        "volume": 100., "turnover": 10_000.,
    })
    m = p[["date", "ticker"]].copy()
    m["security_name"] = "ABC"
    m["shares"] = 1000.
    m["market"] = "KOSPI"
    return p, m, dates


def test_comparison_lists_discrepancies():
    result = compare_calendars(pd.DatetimeIndex(["2026-01-02", "2026-01-05"]),
                               pd.DatetimeIndex(["2026-01-02", "2026-01-06"]))
    assert result["reference_only_dates"] == ["2026-01-06"]
    assert result["observed_only_dates"] == ["2026-01-05"]
    assert not result["matches"]


def test_conservative_split_like_event():
    p, m, dates = example()
    p.loc[20:, ["open", "high", "low", "close"]] *= .5
    m.loc[20:, "shares"] *= 2.
    screened, state, summary = screen_year(p, m, dates)
    assert summary["quarantined_rows"] == 1
    assert screened.iloc[20].unsafe_session
    assert not screened.iloc[19].unsafe_session
    checked = validate_prices(screened).set_index("date")
    labels = make_symbol_targets(checked)
    features = compute_symbol_factors(checked)
    assert np.isnan(labels.loc[dates[15], "forward_return_10"])
    assert np.isnan(labels.loc[dates[20], "forward_return_5"])
    assert np.isfinite(labels.loc[dates[21], "forward_return_5"])
    assert np.isnan(features.loc[dates[20], "ret_5"])
    assert np.isnan(features.loc[dates[30], "rsi_14"])
    assert np.isfinite(features.loc[dates[19], "ret_5"])
    assert len(state) == 1


def test_lookback_cross_file_boundary():
    p, m, dates = example()
    _, prior, _ = screen_year(p.iloc[:20], m.iloc[:20], dates)
    newp, newm = p.iloc[20:].copy(), m.iloc[20:].copy()
    newp.loc[:, ["open", "high", "low", "close"]] *= .5
    newm.loc[:, "shares"] *= 2.
    screened, _, info = screen_year(newp, newm, dates, prior)
    assert screened.iloc[0].unsafe_session
    assert info["suspected_share_count_changes"] == 1


def test_unconfirmed_rename_flagged():
    p, m, dates = example()
    m.loc[10:, "security_name"] = "XYZ"
    _, _, info = screen_year(p, m, dates)
    assert info["security_name_changes"] == 1


def test_invalid_unsafe_flag_rejected():
    p, _, _ = example()
    p["unsafe_session"] = "maybe"
    with pytest.raises(ValueError, match="unsafe_session"):
        validate_prices(p)


def test_source_metadata_market_filter():
    raw = pd.DataFrame({
        "Date": ["2024-01-02"] * 3, "Code": ["5930", "000660", "123456"],
        "Name": ["A", "B", "C"], "Stocks": [100, 200, 300],
        "Market": ["KOSPI", "KOSDAQ", "ETF"],
    })
    metadata = marcap_metadata(raw, 2024)
    assert set(metadata.ticker) == {"005930", "000660"}


def test_reported_official_closure_explanations():
    observed = pd.DatetimeIndex(["2026-06-02", "2026-06-04", "2026-07-16", "2026-07-20"])
    ref = pd.DatetimeIndex(["2026-06-02", "2026-06-03", "2026-06-04",
                            "2026-07-16", "2026-07-17", "2026-07-20"])
    report = compare_calendars(observed, ref)
    assert set(report["reference_only_explained_by_reported_krx_closures"]) == {"2026-06-03", "2026-07-17"}
    assert report["reference_only_still_unexplained"] == []


def test_history_preserves_absent_tickers_across_years():
    prices, metadata, dates = example()
    first, state, _ = screen_year(prices.iloc[:20], metadata.iloc[:20], dates)
    another_price = prices.iloc[20:21].copy()
    another_meta = metadata.iloc[20:21].copy()
    another_price["ticker"] = "000002"
    another_meta["ticker"] = "000002"
    _, state, _ = screen_year(another_price, another_meta, dates, state)
    assert set(state.ticker) == {"000001", "000002"}
