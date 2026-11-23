import pandas as pd
import pytest
from research.k_swing.winner_pairs_v21 import describe_pairs, consistency, PAIRS


def fixture():
    rows = []
    for year in (2019, 2021):
        for i in range(100):
            rows.append({
                "date": f"{year}-06-03", "ticker": f"{i:06d}",
                "ta__stoch_rsi_14": float(i),
                "ta__parkinson_vol_20": float(i),
                "ta__macd_hist_pct": float(i),
                "ta__ichi_cloud_top_gap": float(i),
                "forward_return_5": .07 if i >= 80 else -.02,
                "forward_return_10": .07 if i >= 80 else -.02,
            })
    return pd.DataFrame(rows)


def test_fixed_pairs_enrich_future_winners_but_do_not_prove_profit():
    z = describe_pairs(fixture())
    assert len(z) > 0
    high = z[(z.quadrant == "high_high") & (z.horizon == 5)]
    assert (high.quadrant_winner_rate > high.reference_winner_rate).all()
    s = consistency(z)
    assert s.direction_consistent.any()
    assert not s.after_cost_profit_established.any()
    assert not s.independent_validation.any()


def test_future_year_and_duplicate_rejected():
    x = fixture()
    x.loc[0, "date"] = "2026-01-02"
    with pytest.raises(ValueError, match="2019-22"):
        describe_pairs(x)
    x = fixture()
    with pytest.raises(ValueError, match="Duplicate"):
        describe_pairs(pd.concat([x, x.iloc[[0]]]))


def test_no_missing_factor_silent_substitution():
    with pytest.raises(ValueError, match="Missing preregistered"):
        describe_pairs(fixture().drop(columns=[PAIRS[0][0]]))
