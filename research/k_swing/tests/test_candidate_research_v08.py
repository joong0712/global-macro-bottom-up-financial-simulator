"""Bounded mathematical factor generation: no target leakage and no 2023/26."""
import numpy as np
import pandas as pd
import pytest
from research.k_swing.candidate_research_v08 import (
    BASE,FEATURES,candidate_expressions,daily_rank_ic,evaluate_train_only
)


def make(n=55):
    values={name:np.linspace(.05,.4,n) for name in BASE}
    values["ta__rsi_wilder_14"]=np.linspace(20,80,n)
    values["ta__relative_turnover_20"]=np.linspace(.5,3,n)
    values["ta__roc_20"]=np.linspace(-.2,.2,n)
    return pd.DataFrame(values)


def test_12_formulas_finite_for_valid_values():
    result=candidate_expressions(make())
    assert set(result)==set(FEATURES)
    assert result.shape==(55,12)
    assert np.isfinite(result.to_numpy()).all()


def test_no_future_target_in_candidate_expressions():
    data=make()
    left=candidate_expressions(data)
    data["forward_return_10"]=np.linspace(-99,99,55)
    data["future_trading_date"]="2026-11-11"
    right=candidate_expressions(data)
    pd.testing.assert_frame_equal(left,right)


def test_train_only_split_frozen_before_internal_validation():
    d=pd.bdate_range("2019-01-01","2022-12-30",freq="15B")
    rows=[]
    for dt in d:
        base=candidate_expressions(make(55))
        for idx,item in base.iterrows():
            row={"date":dt,"forward_return_10":float(idx)/1000}
            row.update(item.to_dict())
            rows.append(row)
    annual,summary=evaluate_train_only(pd.DataFrame(rows),horizon=10)
    assert len(summary)==len(FEATURES)
    assert summary.not_independent_confirmation.all()
    assert set(annual.year)=={2019,2020,2021,2022}
    assert summary.train_direction.isin([-1,1]).all()


def test_holdout_and_unexpected_horizon_rejected():
    frame=pd.DataFrame({**{f:[1] for f in FEATURES},
                        "date":["2026-01-02"],"forward_return_5":[0.1]})
    with pytest.raises(ValueError,match="locked"):
        evaluate_train_only(frame,horizon=5)
    with pytest.raises(ValueError,match="only"):
        evaluate_train_only(frame,horizon=11)


def test_spearman_on_per_day_eligible_pairs():
    x=pd.DataFrame({"x":range(50),"y":range(50)})
    assert daily_rank_ic(x,"x","y")==pytest.approx(1.)
