"""Dedup/stability tests: no future-year leakage, proper orientation and group confounds."""
import numpy as np
import pandas as pd
import pytest
from research.k_swing.redundancy_stability_v06 import (
    correlated_clusters,fast_spearman_vector,year_by_year_ic,
)


def _catalog():
    rows=[]
    for h in (5,10):
        for rank,f in enumerate(("ta__alpha","ta__mirror","ta__noise"),1):
            rows.append({"factor":f,"horizon":h,"train_rank_ic":[.8,-.8,.05][rank-1],
                         "direction":[1,-1,1][rank-1],"train_rank":rank})
    return pd.DataFrame(rows)


def test_cluster_identifies_positive_and_negative_duplicates_without_2023():
    dates=pd.bdate_range("2021-01-01",periods=20)
    r=[]
    for day in dates:
        for x in range(30):
            r.append({"date":day,"ta__alpha":float(x),"ta__mirror":float(31-x),
                      "ta__noise":float((x*x+int(day.day))%31)})
    panel=pd.DataFrame(r)
    clusters,edges,report=correlated_clusters(panel,["ta__alpha","ta__mirror","ta__noise"],_catalog(),
                                               threshold=.95,every_nth_session=1,min_pairwise_bars=100)
    group=clusters.set_index("feature").cluster
    assert group["ta__alpha"]==group["ta__mirror"]
    assert report["cluster_count"]>=2
    assert (edges.train_abs_rank_correlation>.95).any()


def test_never_choose_cluster_representative_using_future_period():
    dates=pd.bdate_range("2023-01-01",periods=10)
    d=pd.DataFrame({"date":dates,"ta__alpha":1., "ta__mirror":1.})
    with pytest.raises(ValueError,match="Future"):
        correlated_clusters(d,["ta__alpha","ta__mirror"],_catalog())


def test_fast_spearman_formula_and_valid_pair_handling():
    day=pd.DataFrame({"ta__alpha":np.arange(50.),"ta__mirror":np.arange(50.)[::-1],
                      "forward_return_5":np.arange(50.)})
    day.loc[0,"ta__alpha"]=np.nan
    result=fast_spearman_vector(day,["ta__alpha","ta__mirror"],"forward_return_5")
    assert result["ta__alpha"]==pytest.approx(1.)
    assert result["ta__mirror"]==pytest.approx(-1.)


def test_stability_uses_training_directions_and_2023_only_as_reused_year():
    dates=pd.bdate_range("2022-12-01",periods=60)
    data=[]
    for day in dates:
        for i in range(45):
            data.append({"date":day,"ta__alpha":float(i),"ta__mirror":float(45-i),
                         "ta__noise":float((7*i+int(day.day))%45),
                         "forward_return_5":float(i),"forward_return_10":float(i)})
    a,b=year_by_year_ic(pd.DataFrame(data),_catalog(),n_train_candidates=2)
    assert set(a.year)=={2022,2023}
    assert len(b)==4
    assert b.loc[b.factor.eq("ta__mirror"),"exploratory_2023_ic"].gt(.9).all()
    assert b.loc[b.factor.eq("ta__alpha"),"exploratory_2023_ic"].gt(.9).all()


def test_inspected_future_2024_rejected():
    d=pd.DataFrame({"date":pd.to_datetime(["2024-01-01"]),"ta__alpha":[1.],
                    "forward_return_5":[0.],"forward_return_10":[0.]})
    with pytest.raises(ValueError,match="2024"):
        year_by_year_ic(d,_catalog())
