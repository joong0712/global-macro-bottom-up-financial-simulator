import pandas as pd
import pytest
from research.k_swing.winner_risk_reward_v23 import analyze, incremental, VOL, SECONDARY

def fixture():
    rows=[]
    for year in (2019,2021):
        for i in range(200):
            rows.append({"date":f"{year}-06-03","ticker":f"{i:06d}",
                         VOL:float(i), **{k:float(i) for k in SECONDARY},
                         "forward_return_5":.08 if i>=160 else (-.06 if i<40 else 0),
                         "forward_return_10":.08 if i>=160 else (-.06 if i<40 else 0)})
    return pd.DataFrame(rows)

def test_up_down_and_net_cost():
    result=analyze(fixture())
    top=result[(result.period=="2019_20")&(result.horizon==5)&(result.cohort=="high_vol")].iloc[0]
    assert top.up_5_pct==1
    assert top.down_5_pct==0
    assert top.mean_net_50bps_pct==pytest.approx(7.5)
    assert len(incremental(result))==12

def test_holdout_and_duplicates_blocked():
    x=fixture()
    x.loc[0,"date"]="2026-01-02"
    with pytest.raises(ValueError,match="holdout"): analyze(x)
    x=fixture()
    with pytest.raises(ValueError,match="duplicate"): analyze(pd.concat([x,x.iloc[[0]]]))

def test_missing_factor_rejected():
    with pytest.raises(ValueError,match="missing"): analyze(fixture().drop(columns=[VOL]))
