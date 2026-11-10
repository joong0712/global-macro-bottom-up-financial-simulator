"""Sample pilot is exploratory, contains no future test-period selection."""
import numpy as np
import pandas as pd
import pytest
from research.k_swing.factor_pilot_v04 import is_sampled, _metrics_for_day, aggregate, TOP_K


def test_hash_sampling_stable_and_not_current_listing_filter():
    assert is_sampled("005930") == is_sampled("005930")
    with pytest.raises(ValueError, match="modulus"):
        is_sampled("005930", 0)


def test_daily_factor_ic_and_multiple_topk():
    date = pd.Timestamp("2022-04-01")
    day = pd.DataFrame({
        "date": [date] * 50, "ta__trend": np.arange(50),
        "legacy__ret": np.arange(50)[::-1],
        "forward_return_5": np.arange(50) / 1000,
    })
    records = _metrics_for_day(day, ["ta__trend", "legacy__ret"], "forward_return_5", 5)
    assert len(records) == 2
    row = next(r for r in records if r["factor"] == "ta__trend")
    assert row["rank_ic_raw"] == pytest.approx(1.0)
    assert row["high_1"] == pytest.approx(.049)
    assert row["high_20"] > row["low_20"]
    assert len(TOP_K) == 5


def _fake_daily():
    dates = pd.bdate_range("2020-01-01", periods=10).append(
        pd.bdate_range("2023-03-01", periods=5))
    rows = []
    for year in (5, 10):
        for fac in ("high", "low"):
            for d in dates:
                rank = (.7 if fac == "high" else -.5) if d.year < 2023 else -.2
                row = {
                    "date": str(d.date()), "year": d.year, "factor": fac,
                    "horizon": year, "cross_section": 60,
                    "rank_ic_raw": rank, "universe_mean": .001,
                }
                for k in TOP_K:
                    row[f"high_{k}"] = .01
                    row[f"low_{k}"] = -.01
                rows.append(row)
    return pd.DataFrame(rows)


def test_factor_direction_and_ranking_train_only():
    origin = _fake_daily()
    m, t = aggregate(origin, min_train_dates=5)
    assert set(m.split) == {"train", "validation_2023_reused"}
    assert t.loc[(t.factor == "low") & (t.horizon == 5), "direction"].iloc[0] == -1
    mutated = origin.copy()
    mutated.loc[mutated.year == 2023, "rank_ic_raw"] = 99
    _, changed = aggregate(mutated, min_train_dates=5)
    pd.testing.assert_frame_equal(t.reset_index(drop=True), changed.reset_index(drop=True))
