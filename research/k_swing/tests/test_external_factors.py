"""Timestamp, market regime and benchmark inputs must not leak future values."""
import numpy as np
import pandas as pd
import pytest
from research.k_swing.external_point_in_time import (
    join_dart_fundamentals, join_investor_flows, join_macro_releases,
)
from research.k_swing.relative_strength import compute_relative_strength


def test_dart_after_close_appears_next_session():
    signals = pd.DataFrame({"date": ["2024-03-14", "2024-03-15", "2024-03-18"],
                            "ticker": ["005930"] * 3})
    docs = pd.DataFrame({"ticker": ["005930"],
                         "available_at": ["2024-03-15T16:01:00+09:00"],
                         "sales": [1250.]})
    x = join_dart_fundamentals(signals, docs, ["sales"])
    assert pd.isna(x.sales.iloc[0]) and pd.isna(x.sales.iloc[1])
    assert x.sales.iloc[2] == 1250


def test_pit_revision_not_applied_to_earlier_signals():
    signals = pd.DataFrame({"date": ["2024-01-08", "2024-01-09", "2024-01-10"],
                            "ticker": ["000001"] * 3})
    docs = pd.DataFrame({"ticker": ["000001", "000001"],
                         "available_at": ["2024-01-08T14:00:00+09:00", "2024-01-09T18:00:00+09:00"],
                         "sales": [100, 200]})
    result = join_dart_fundamentals(signals, docs, ["sales"])
    assert result.sales.tolist() == [100, 100, 200]


def test_investor_flow_and_timezone_strictness():
    signals = pd.DataFrame({"date": ["2024-01-04"], "ticker": ["000001"]})
    for release in ["2024-01-04T16:01:00", "2024-01-04 16:01:00"]:
        docs = pd.DataFrame({"ticker": ["000001"], "available_at": [release], "net": [50]})
        with pytest.raises(ValueError, match="timezone-aware"):
            join_investor_flows(signals, docs, ["net"])
    docs = pd.DataFrame({"ticker": ["000001"], "available_at": ["2024-01-04T16:01:00+09:00"], "net": [50]})
    assert pd.isna(join_investor_flows(signals, docs, ["net"]).net.iloc[0])


def test_macro_release_delayed_to_next_day():
    signal = pd.DataFrame({"date": ["2024-01-04", "2024-01-05"], "series_id": ["KR_RATE"] * 2})
    events = pd.DataFrame({"series_id": ["KR_RATE"],
                           "available_at": ["2024-01-04T16:00:00+09:00"], "rate": [3.5]})
    out = join_macro_releases(signal, events, ["rate"])
    assert pd.isna(out.rate.iloc[0])
    assert out.rate.iloc[1] == pytest.approx(3.5)


def _stocks_and_benchmark():
    dates = pd.bdate_range("2024-01-02", periods=70)
    stocks = pd.DataFrame({
        "date": dates, "ticker": ["000001"] * len(dates),
        "close": np.linspace(100, 130, len(dates)),
        "market_benchmark_id": ["KOSPI"] * len(dates),
        "sector_benchmark_id": ["SEMIS"] * len(dates),
    })
    bench = pd.DataFrame({
        "date": list(dates) * 2,
        "benchmark_id": ["KOSPI"] * len(dates) + ["SEMIS"] * len(dates),
        "close": list(np.linspace(1000, 1100, len(dates))) + list(np.linspace(600, 720, len(dates))),
    })
    return stocks, bench


def test_relative_strength_matches_manual_market_calculation():
    stocks, benchmarks = _stocks_and_benchmark()
    out = compute_relative_strength(stocks, benchmarks)
    i = len(stocks) - 1
    expected = (stocks.close.iloc[i] / stocks.close.iloc[i - 5]) / (
        1100 / np.linspace(1000, 1100, len(stocks))[i - 5]
    ) - 1
    assert out.rs_market_5.iloc[-1] == pytest.approx(expected)
    assert out.rs_sector_5.iloc[-1] != pytest.approx(out.rs_market_5.iloc[-1])
    assert np.isfinite(out.market_beta_60.iloc[-1])


def test_missing_sector_data_is_never_fabricated():
    stocks, benchmarks = _stocks_and_benchmark()
    benchmarks = benchmarks.loc[benchmarks.benchmark_id.eq("KOSPI")]
    out = compute_relative_strength(stocks, benchmarks)
    assert out.rs_market_5.notna().sum() > 0
    assert out.rs_sector_5.isna().all()


def test_future_mutation_does_not_affect_past_relative_features():
    stocks, benchmarks = _stocks_and_benchmark()
    base = compute_relative_strength(stocks, benchmarks)
    changed = stocks.copy()
    changed.loc[55:, "close"] *= 2
    after = compute_relative_strength(changed, benchmarks)
    pd.testing.assert_frame_equal(base.iloc[:55], after.iloc[:55])


def test_calendar_gap_cannot_count_as_consecutive_bars():
    stocks, benchmarks = _stocks_and_benchmark()
    stocks = stocks.drop(stocks.index[30]).reset_index(drop=True)
    result = compute_relative_strength(stocks, benchmarks)
    assert pd.isna(result.loc[32, "rs_market_5"])


def test_ambiguous_same_timestamp_filing_rejected():
    s = pd.DataFrame({"date": ["2024-02-01"], "ticker": ["000001"]})
    events = pd.DataFrame({"ticker": ["000001", "000001"],
                           "available_at": ["2024-02-01T14:00:00+09:00"] * 2,
                           "value": [1, 2]})
    with pytest.raises(ValueError, match="ambiguous"):
        join_dart_fundamentals(s, events, ["value"])


def test_mixed_utc_and_korean_release_formats_are_normalized():
    signals = pd.DataFrame({"date": ["2024-01-04", "2024-01-04", "2024-01-05", "2024-01-05"],
                            "ticker": ["000001", "000002", "000001", "000002"]})
    events = pd.DataFrame({
        "ticker": ["000001", "000002"],
        "available_at": ["2024-01-04T00:00:00Z", "2024-01-04T16:01:00+09:00"],
        "flow": [100, 200],
    })
    out = join_investor_flows(signals, events, ["flow"])
    assert out.flow.iloc[0] == 100
    assert pd.isna(out.flow.iloc[1])
    assert out.flow.iloc[2] == 100
    assert out.flow.iloc[3] == 200


def test_pit_join_does_not_silently_replace_existing_signal_field():
    signals = pd.DataFrame({"date": ["2024-01-04"], "ticker": ["000001"], "revenue": [100]})
    filings = pd.DataFrame({"ticker": ["000001"],
                            "available_at": ["2024-01-03T12:00:00+09:00"], "revenue": [200]})
    with pytest.raises(ValueError, match="already exist"):
        join_dart_fundamentals(signals, filings, ["revenue"])
