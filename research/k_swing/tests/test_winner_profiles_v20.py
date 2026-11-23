import numpy as np
import pandas as pd
import pytest
from research.k_swing.winner_profiles_v20 import profile, summarize


def sample():
    dates = list(pd.date_range("2019-01-02", periods=4, freq="B")) + list(
        pd.date_range("2021-01-04", periods=4, freq="B"))
    rows = []
    for d in dates:
        for i in range(100):
            rows.append({"date": d, "ticker": f"{i:06d}",
                         "ta__momentum": float(i),
                         "legacy__reversal": -float(i),
                         "forward_return_5": .08 if i >= 80 else -.01,
                         "forward_return_10": .08 if i >= 80 else -.01})
    return pd.DataFrame(rows)


def test_winner_enrichment_is_observed_in_both_windows():
    p = profile(sample())
    x = p.loc[p.factor.eq("ta__momentum")]
    assert len(x) == 2
    assert (x.top_quintile_winner_rate > x.bottom_quintile_winner_rate).all()
    s = summarize(p)
    x = s.loc[s.factor.eq("ta__momentum")].iloc[0]
    assert bool(x.direction_consistent)
    assert not bool(x.profitable_strategy_established)


def test_reversed_factor_sign():
    s = summarize(profile(sample()))
    x = s.loc[s.factor.eq("legacy__reversal")].iloc[0]
    assert x.direction_train == -1
    assert x.direction_check == -1


def test_2026_locked_and_no_missing_factors():
    a = sample()
    a["date"] = pd.Timestamp("2026-01-02")
    with pytest.raises(ValueError, match="2019-22"):
        profile(a)
    with pytest.raises(ValueError, match="No precomputed"):
        profile(sample().drop(columns=["ta__momentum", "legacy__reversal"]))


def test_duplicate_ticker_date_rejected():
    a = sample()
    with pytest.raises(ValueError, match="Duplicate"):
        profile(pd.concat([a, a.iloc[[0]]], ignore_index=True))


def test_predeclared_rise_threshold_only():
    with pytest.raises(ValueError, match="Predeclared"):
        profile(sample(), rise_threshold=.01)
