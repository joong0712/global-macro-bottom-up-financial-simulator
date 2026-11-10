"""v0.4 real-study matrix adapter smoke checks on synthetic screen-cleaned bars."""
import numpy as np
import pandas as pd
import pytest
from research.k_swing.factor_matrix_v04 import private_matrix, one_symbol_matrix


def sample(n=430, tickers=3):
    dates = pd.bdate_range("2023-01-02", periods=n)
    rows = []
    for k in range(tickers):
        x = np.arange(n, dtype=float)
        close = 4000 + x * (1 + k/5) + np.sin(x/9) * 35
        opening = close + np.cos(x / 4 + k) * 20
        vol = 200000 + x * 50 + k * 100
        rows.append(pd.DataFrame({
            "date": dates, "ticker": f"{k+1:06d}",
            "open": opening, "high": np.maximum(close, opening)*1.01,
            "low": np.minimum(close, opening)*.99, "close": close,
            "volume": vol, "turnover": vol * close, "unsafe_session": False,
        }))
    return pd.concat(rows, ignore_index=True), dates


def test_matrix_has_original_plus_expanded_and_future_labels():
    data, dates = sample()
    result = one_symbol_matrix(data.loc[data.ticker=="000001"], dates,
                               "2024-01-02", "2024-05-30")
    assert len(result) > 30
    legacy = [x for x in result if x.startswith("legacy__")]
    ext = [x for x in result if x.startswith("ta__")]
    assert len(legacy) == 18
    assert len(ext) >= 170
    assert "ta__ichi_cloud_top_gap" in result
    assert "forward_return_5" in result


def test_confirmation_data_is_locked_before_read(tmp_path):
    data, dates = sample()
    p = tmp_path / "screened.csv.gz"
    data.to_csv(p, index=False, compression="gzip")
    c = tmp_path / "dates.csv"
    pd.DataFrame({"date": dates}).to_csv(c, index=False)
    with pytest.raises(ValueError, match="2026 confirmation set is locked"):
        private_matrix([p], c, tmp_path / "private", signal_start="2025-01-01",
                       signal_end="2026-04-01")


def test_suspicious_signal_masks_recent_ichimoku_and_target():
    data, dates = sample()
    data.loc[(data.ticker=="000001") & data.date.eq(dates[300]), "unsafe_session"] = True
    out = one_symbol_matrix(data[data.ticker=="000001"], dates,
                            str(dates[290].date()), str(dates[318].date()))
    safe = out.set_index("date")
    assert pd.isna(safe.loc[dates[300], "ta__ichi_cloud_top_gap"])
    assert pd.isna(safe.loc[dates[296], "forward_return_10"])


def test_private_matrix_writes_partitions_and_manifest(tmp_path):
    data, dates = sample()
    p = tmp_path / "screened.csv.gz"
    data.to_csv(p, index=False, compression="gzip")
    calendar = tmp_path / "calendar.csv"
    pd.DataFrame({"date": dates}).to_csv(calendar, index=False)
    manifest = private_matrix([p], calendar, tmp_path / "features",
                              signal_start="2024-01-02", signal_end="2024-05-30",
                              batch_tickers=2)
    assert manifest["old_indicator_count"] == 18
    assert manifest["new_indicator_count"] >= 170
    assert len(manifest["parts"]) == 2
    assert manifest["holdout_2026_opened"] is False
    s = pd.read_parquet(tmp_path / "features" / manifest["parts"][0])
    assert s["ticker"].nunique() == 2
