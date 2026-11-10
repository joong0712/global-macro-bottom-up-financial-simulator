"""v0.3 tests: data gates, non-leaky factor selection, liquidity, embargo."""
import json

import numpy as np
import pandas as pd
import pytest

from research.k_swing.factor_real_experiment import (
    FACTOR_NAMES, _daily_cohorts, _load_year, summarize, validate_market_quality,
)


def test_calendar_fails_closed_on_unknown_gap():
    with pytest.raises(ValueError, match="Unexplained"):
        validate_market_quality({"calendar": {
            "reference_only_dates": ["2021-02-01"], "observed_only_dates": []
        }})


def test_documented_ad_hoc_holidays_permitted_with_warning():
    data = validate_market_quality({"calendar": {
        "reference_only_dates": ["2026-06-03", "2026-07-17"],
        "observed_only_dates": []
    }})
    assert data["reference_only"] == ["2026-06-03", "2026-07-17"]


def _synthetic_daily_metrics():
    dates_train = pd.bdate_range("2020-01-01", periods=20)
    dates_valid = pd.bdate_range("2023-01-01", periods=5)
    dates_test = pd.bdate_range("2024-01-01", periods=6)
    records = []
    for horizon in (5, 10):
        for i, factor in enumerate(FACTOR_NAMES):
            for date in dates_train.append(dates_valid).append(dates_test):
                if date.year <= 2022:
                    ic = 0.5 if i == 0 else (-.4 if i == 1 else .01)
                elif date.year == 2023:
                    ic = -.5 if i == 0 else .5
                else:
                    ic = -.9 if i == 0 else .8
                records.append({
                    "date": date, "year": date.year, "factor": factor, "horizon": horizon,
                    "rank_ic_raw": ic, "high_topk_gross": .04,
                    "low_topk_gross": -.02, "high_topk_win": .9,
                    "low_topk_win": .1, "universe_mean_return": .005,
                    "n_eligible_for_factor": 120, "universe_n": 120,
                })
    return pd.DataFrame(records)


def test_direction_selection_never_uses_validation_or_test():
    base = _synthetic_daily_metrics()
    m1, s1, _ = summarize(base, min_training_dates=10)
    changed = base.copy()
    changed.loc[changed.year >= 2023, "rank_ic_raw"] *= -1
    _, s2, _ = summarize(changed, min_training_dates=10)
    pd.testing.assert_frame_equal(s1.reset_index(drop=True), s2.reset_index(drop=True))
    chosen = s1.loc[(s1.factor == "ret_5") & (s1.horizon == 5)]
    assert int(chosen.direction.iloc[0]) == -1
    assert set(m1.split) == {"train", "validation", "test"}


def test_cost_subtraction_and_baseline_are_descriptive():
    metrics, _, _ = summarize(_synthetic_daily_metrics(), roundtrip_bps=30,
                              min_training_dates=10)
    row = metrics.loc[(metrics.split == "test") &
                      (metrics.factor == FACTOR_NAMES[0]) &
                      (metrics.horizon == 5)].iloc[0]
    assert row.topk_avg_net_approx == pytest.approx(row.topk_avg_gross_return - .003)
    assert row.topk_avg_excess_gross == pytest.approx(
        row.topk_avg_gross_return - row.universe_avg_gross_return
    )


def test_no_future_signal_eligibility_leak():
    dates = [pd.Timestamp("2024-02-01"), pd.Timestamp("2024-02-02")]
    records = []
    for d in dates:
        for i in range(7):
            record = dict(date=d, ticker=f"{i+1:06d}", turnover=2e8,
                          close=1000., volume=10., unsafe_session=False,
                          forward_return_5=i / 100, forward_return_10=i / 200)
            record.update({name: float(i + 1) for name in FACTOR_NAMES})
            records.append(record)
    panel = pd.DataFrame(records)
    panel.loc[panel.ticker.eq("000007"), "turnover"] = 0
    panel.loc[panel.ticker.eq("000006"), "unsafe_session"] = True
    daily = _daily_cohorts(panel, 2024, min_turnover=1e8, min_price=1000,
                           min_names=5, top_k=2, embargo_dates={dates[1]})
    assert len(daily) == 2 * len(FACTOR_NAMES)
    assert all(x["date"] == dates[0] for x in daily)
    assert all(x["n_eligible_for_factor"] == 5 for x in daily)


def test_non_screened_prices_rejected(tmp_path):
    pd.DataFrame({"date": ["2024-01-02"], "ticker": ["005930"], "close": [100.]}
                 ).to_csv(tmp_path / "kswing_screened_2024.csv.gz",
                          index=False, compression="gzip")
    with pytest.raises(ValueError, match="not v0.2 screened"):
        _load_year(tmp_path, 2024)


def test_empty_metrics_fail_closed():
    with pytest.raises(ValueError, match="No factor"):
        summarize(pd.DataFrame())
