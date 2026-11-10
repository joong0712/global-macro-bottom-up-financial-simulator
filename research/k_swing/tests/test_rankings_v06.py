"""Reproducible leaderboard refuses future datasets or duplicate joins."""
import numpy as np
import pandas as pd
import pytest
from research.k_swing.rankings_v06 import build, TOP_K


def example():
    tr, ag = [], []
    for horizon in (5,10):
        for f, ic in (("alpha", .2), ("beta", -.4)):
            tr.append({"factor":f,"horizon":horizon,"train_rank_ic":ic,
                       "train_days":300,"direction":1 if ic>0 else -1,
                       "train_rank":1 if f=="beta" else 2,"eligible":True})
            for period, excess in (("train",.01),("validation_2023_reused",.03 if f=="alpha" else -.02)):
                r={"factor":f,"horizon":horizon,"split":period,"signal_days":300,
                   "mean_oriented_rank_ic":abs(ic),"direction_from_train":1 if ic>0 else -1}
                for k in TOP_K:
                    r[f"avg_top{k}_excess_gross"]=excess
                ag.append(r)
    return pd.DataFrame(ag),pd.DataFrame(tr)


def test_topk_leaderboard_and_train_directions():
    a,t=example()
    out=build(a,t)
    assert len(out)==2*2*len(TOP_K)
    best=out[(out.horizon==10)&(out.top_k==10)].iloc[0]
    assert best.factor=="alpha"
    assert best.explored_2023_avg_excess_gross==pytest.approx(.03)
    assert best.explored_2023_excess_minus_assumed_100bps==pytest.approx(.02)
    assert best.train_ic_rank==2


def test_future_or_unknown_splits_refused():
    a,t=example()
    a.loc[0,"split"]="test_2026"
    with pytest.raises(ValueError,match="Only train"):
        build(a,t)


def test_invalid_orientation_and_duplicates_rejected():
    a,t=example()
    t.loc[0,"direction"]*=-1
    with pytest.raises(ValueError,match="orientation"):
        build(a,t)
    a,t=example()
    with pytest.raises(ValueError,match="Duplicate"):
        build(pd.concat([a,a.iloc[[0]]]),t)
