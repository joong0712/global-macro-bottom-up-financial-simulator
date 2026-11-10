"""Deterministic tests, no exchange data or network required."""
import pandas as pd
import pytest
from research.k_swing.marcap_ingest import normalize_marcap, url_for


def fixture_rows():
    return pd.DataFrame({
        "Date": ["2024-02-01", "2024-02-01", "2024-02-01", "2024-02-02", "2024-02-02"],
        "Code": ["5930", "000660", "123456", "005930", "000660"],
        "Market": ["KOSPI", "KOSPI", "ETF", "KOSPI", "KOSDAQ"],
        "Open": [100, 200, 300, 105, 205],
        "High": [110, 220, 320, 112, 220],
        "Low": [95, 190, 290, 100, 195],
        "Close": [105, 210, 310, 110, 215],
        "Volume": [100, 1000, 1000, 150, 0],
        "Amount": [10000, 200000, 300000, 15000, 0],
    })


def test_market_filter_and_zero_volume_retention():
    df, audit = normalize_marcap(fixture_rows(), 2024)
    assert len(df) == 4 and audit["zero_volume_or_turnover_rows"] == 1
    assert df.iloc[0]["ticker"] == "000660" or "005930" in set(df["ticker"])


def test_nonunique_index():
    src = fixture_rows()
    src.index = [pd.Timestamp("2024-02-01")] * len(src)
    df, _ = normalize_marcap(src, 2024)
    assert len(df) == 4


def test_year_boundary_and_duplicate_guard():
    src = fixture_rows()
    src.loc[0, "Date"] = "2023-12-29"
    df, audit = normalize_marcap(src, 2024)
    assert len(df) == 3 and audit["dropped_wrong_year_rows"] == 1
    with pytest.raises(ValueError, match="duplicate"):
        normalize_marcap(pd.concat([fixture_rows(), fixture_rows().iloc[[0]]]), 2024)


def test_invalid_ohlc_and_missing_columns():
    src = fixture_rows()
    src.loc[0, "High"] = 1
    df, audit = normalize_marcap(src, 2024)
    assert audit["dropped_quality_rows"] == 1 and len(df) == 3
    with pytest.raises(ValueError, match="missing columns"):
        normalize_marcap(src.drop(columns="Amount"), 2024)


def test_pinned_ref_validation():
    assert url_for(2024).endswith("/data/marcap-2024.parquet")
    with pytest.raises(ValueError, match="git ref"):
        url_for(2024, "../../master")
