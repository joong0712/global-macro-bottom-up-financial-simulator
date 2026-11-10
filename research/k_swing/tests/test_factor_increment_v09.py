"""Same-stock universe, train-only decisions, no 2023-or-later leakage."""
import numpy as np
import pandas as pd
import pytest
from research.k_swing.factor_increment_v09 import (
    matched_day_metrics,circular_block_ci,assess_daily,BASELINES
)


def test_same_stock_pairwise_complete_for_baselines_and_candidate():
    n=50
    day=pd.DataFrame({
        "candidate":np.arange(n,dtype=float),
        BASELINES[0]:np.arange(n,dtype=float)[::-1],
        BASELINES[1]:(np.arange(n,dtype=float)*7)%51,
        "forward_return_10":np.arange(n,dtype=float),
    })
    day.loc[0,"candidate"]=np.nan
    x=matched_day_metrics(day,"candidate","forward_return_10")
    assert x["matched_stocks"]==49
    assert x["candidate_raw_ic"]==pytest.approx(1.,abs=1e-12)
    assert x["atr_lowvol_ic"]==pytest.approx(1.,abs=1e-12)


def test_degenerate_baseline_never_claims_independent_partial_ic():
    n=45
    day=pd.DataFrame({
        "c":np.arange(n,dtype=float),
        BASELINES[0]:np.arange(n,dtype=float)[::-1],
        BASELINES[1]:np.arange(n,dtype=float)[::-1],
        "y":np.arange(n,dtype=float),
    })
    r=matched_day_metrics(day,"c","y")
    assert np.isnan(r["candidate_partial_ic_given_both_vol_controls"])


def test_stronger_candidate_oriented_same_stock_comparison():
    dates=pd.bdate_range("2019-01-02","2022-12-28",freq="B")
    rows=[]
    for date in dates:
        sign=1
        rows.append({
            "date":date,"candidate":"new_factor","horizon":10,"matched_stocks":60,
            "candidate_raw_ic":.16 if date.year<=2020 else .10,
            "atr_lowvol_ic":.08,
            "parkinson_lowvol_ic":.07,
            "candidate_partial_ic_given_both_vol_controls":.04,
        })
        rows.append({
            "date":date,"candidate":"new_factor","horizon":5,"matched_stocks":60,
            "candidate_raw_ic":.12 if date.year<=2020 else .09,
            "atr_lowvol_ic":.06,
            "parkinson_lowvol_ic":.05,
            "candidate_partial_ic_given_both_vol_controls":.03,
        })
    result,annual=assess_daily(pd.DataFrame(rows))
    assert len(result)==4
    assert len(annual)==8
    assert result.loc[result.period.eq("internal_2021_22"),
                      "paired_mean_ic_improvement"].gt(0).all()
    assert result.baseline_frozen_in_2019_20.eq(BASELINES[0]).all()


def test_2023_and_2026_days_cannot_enter_selection():
    dates=pd.bdate_range("2023-01-02",periods=200)
    df=pd.DataFrame({"date":dates,"candidate":"any","horizon":10,
                     "candidate_raw_ic":.1,"atr_lowvol_ic":.1,
                     "parkinson_lowvol_ic":.09,
                     "matched_stocks":50,"candidate_partial_ic_given_both_vol_controls":.05})
    with pytest.raises(ValueError,match="locked"):
        assess_daily(df)


def test_bootstrap_is_deterministic_and_rejects_short_samples():
    x=np.arange(80,dtype=float)/100
    assert circular_block_ci(x,draws=110,block=10,seed=44)==circular_block_ci(
        x,draws=110,block=10,seed=44)
    with pytest.raises(ValueError,match="insufficient"):
        circular_block_ci(x[:10],block=10)
