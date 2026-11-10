"""v0.5 tests: market/size confounds, costs and next-day non-fill reporting."""
from pathlib import Path
import numpy as np
import pandas as pd
import pytest
from research.k_swing.controls_v05 import (
    FROZEN_LOW_VOL_FACTORS, assign_size_buckets,
    cohort_friction, controlled_daily_ic, read_yearly_size_market_data
)


def test_size_quantiles_stratify_by_market_and_signal_day():
    day = pd.Timestamp("2022-03-04")
    data = pd.DataFrame({
        "date":[day] * 12,
        "market":["KOSPI"]*6+["KOSDAQ"]*6,
        "market_cap_krw":list(range(1,7))+list(range(100,106)),
    })
    result = assign_size_buckets(data)
    for market in ["KOSPI","KOSDAQ"]:
        q = result.loc[result.market.eq(market),"size_bucket"].to_list()
        assert q == [0, 1, 1, 2, 2, 2] or q == [0, 0, 1, 1, 2, 2]
        assert set(q) == {0, 1, 2}


def test_market_size_confounded_ic_flips_within_groups():
    rows = []
    # Strong positive between groups, negative within every stratum.
    for market_num, market in enumerate(("KOSPI","KOSDAQ")):
        for bucket in range(3):
            level = market_num * 500 + bucket * 100
            for i in range(18):
                rows.append({
                    "market":market,"size_bucket":bucket,
                    "ta__factor":float(level+i),"forward_return_5":float(level-i),
                })
    data = pd.DataFrame(rows)
    result = controlled_daily_ic(data,"ta__factor","forward_return_5")
    assert result["groups"] == 6
    assert result["ic_raw"] > .8
    assert result["ic_neutral"] < -.95


def test_no_future_label_filter_or_hindsight_replacement():
    day = pd.DataFrame({
        "ticker":["000001","000002","000003","000004","000005"],
        "ta__factor":[.01,.02,.03,.04,.05],
        "turnover":[2e9,1e8,2e9,2e9,2e9],
        "forward_return_5":[np.nan,.05,.10,.30,.50],
    })
    metrics = cohort_friction(day,"ta__factor","forward_return_5",top_k=3)
    assert metrics["picked"] == 3
    assert metrics["evaluable"] == 2
    assert metrics["unresolved"] == 1
    assert metrics["gross"] == pytest.approx(.075)
    assert metrics["capacity_pass"] == 2
    assert metrics["net_bps_100"] == pytest.approx(.065)


def test_cost_stress_is_monotonic_without_false_net_profit_claim():
    day = pd.DataFrame({
        "ticker":["000001","000002","000003"],
        "ta__factor":[1,2,3],
        "turnover":[4e9]*3,
        "forward_return_10":[.01,.03,.04],
    })
    m = cohort_friction(day,"ta__factor","forward_return_10",top_k=3)
    assert m["net_bps_20"] > m["net_bps_50"] > m["net_bps_100"] > m["net_bps_200"]


def test_metadata_market_cap_source_and_duplicate_guard(tmp_path):
    raw = pd.DataFrame({
        "Date":["2023-01-02","2023-01-02","2023-01-02"],
        "Code":["5930","000660","123456"],
        "Market":["KOSPI","KOSDAQ","ETF"],
        "Marcap":[10_000,20_000,30_000],
    })
    (tmp_path/"_raw").mkdir()
    raw.to_parquet(tmp_path/"_raw"/"marcap-2023.parquet",index=False)
    out = read_yearly_size_market_data(tmp_path,(2023,))
    assert set(out.ticker) == {"005930","000660"}
    assert out.market_cap_krw.sum() == 30_000
    raw = pd.concat([raw,raw.iloc[[0]]])
    raw.to_parquet(tmp_path/"_raw"/"marcap-2023.parquet",index=False)
    with pytest.raises(ValueError,match="Ambiguous"):
        read_yearly_size_market_data(tmp_path,(2023,))


def test_no_unsupported_sector_inputs_claimed():
    assert set(FROZEN_LOW_VOL_FACTORS) == {
        "ta__atr_wilder_pct_7","ta__parkinson_vol_20",
        "ta__garman_klass_vol_20","legacy__atr_pct_14","ta__realized_vol_60"
    }
    with pytest.raises(ValueError):
        assign_size_buckets(pd.DataFrame({"market":["KOSPI"]}))
