import pytest
from research.k_swing.cost_frontier_v19 import analyze


def test_no_strategy_positive_at_50bps_both_periods():
    report = analyze()
    assert len(report["rows"]) == 8
    assert all(not x["positive_at_50bps"] for x in report["rows"])
    assert all(not v["positive_at_50bps_both_periods_for_any_fixed_horizon"]
               for v in report["by_entry"].values())


def test_gross_addback_and_break_even():
    r = next(r for r in analyze()["rows"]
             if r["entry"] == "ichi_ma" and r["period"] == "2019-20"
             and r["horizon_sessions"] == 10)
    assert r["implied_mean_zero_cost_percent"] == pytest.approx(.422)
    assert r["break_even_roundtrip_bps"] == pytest.approx(42.2)
    assert r["positive_at_assumed_costs_bps"]["20"] is True
    assert r["positive_at_assumed_costs_bps"]["50"] is False


def test_negative_even_at_zero_cost():
    r = next(r for r in analyze()["rows"]
             if r["entry"] == "vcr_trend" and r["period"] == "2019-20")
    assert r["implied_mean_zero_cost_percent"] == pytest.approx(-1.616)
    assert r["positive_at_assumed_costs_bps"]["0"] is False


def test_no_2026_or_live_orders():
    report = analyze()
    assert not report["2026_holdout_touched"]
    assert not report["real_orders_allowed"]
    assert report["data_reused_not_independent"]


def test_invalid_cost_grid_rejected():
    with pytest.raises(ValueError):
        analyze((-10, 50))
