"""Statistical guards for multiple comparison and blocked forward labels."""
import numpy as np
import pandas as pd
import pytest
from research.k_swing.statistical_stress_v07 import bh_qvalues,block_diagnostics


def test_bh_monotonic_and_fdr():
    q=bh_qvalues(np.array([.05,.001,.02]))
    assert q[1]==pytest.approx(.003)
    assert q[2]==pytest.approx(.03)
    assert q[0]==pytest.approx(.05)


def test_block_qa_uses_reused_2023_and_declares_nonconfirmatory():
    dates=pd.bdate_range("2023-01-02",periods=75)
    rng=np.random.default_rng(94)
    rows=[]
    for d in dates:
        for name,mu in (("volatility",.12),("noise",0.)):
            rows.append({"date":d,"factor":name,"horizon":10,
                         "oriented_ic":float(np.clip(mu+rng.normal(0,.06),-1,1))})
    result=block_diagnostics(pd.DataFrame(rows),n_iter=150,block_sessions=15,seed=101)
    assert len(result)==2
    assert result.not_independent_confirmation.all()
    vol=result.set_index("factor").loc["volatility"]
    noise=result.set_index("factor").loc["noise"]
    assert vol.mean_oriented_ic > noise.mean_oriented_ic
    assert 0 < vol.bh_exploratory_q <= 1
    assert vol.block_bootstrap_ci95_low <= vol.mean_oriented_ic <= vol.block_bootstrap_ci95_high


def test_2024_opening_refused():
    df=pd.DataFrame({"date":pd.bdate_range("2024-01-02",periods=65).repeat(2),
                     "factor":["a","b"]*65,"horizon":[10]*130,
                     "oriented_ic":np.ones(130)*.1})
    with pytest.raises(ValueError,match="only"):
        block_diagnostics(df,n_iter=100,block_sessions=10)


def test_unusable_pvalue_rejected():
    with pytest.raises(ValueError):
        bh_qvalues(np.array([np.nan,.2]))
