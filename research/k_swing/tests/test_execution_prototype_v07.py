"""T+1 execution and cash/unknown-exit guards."""
import pandas as pd
import numpy as np
import pytest
from research.k_swing.execution_prototype_v07 import simulate


def inputs():
    dates=pd.bdate_range("2023-01-02",periods=31)
    bars=pd.DataFrame([{"date":d,"ticker":t,"open":p,"close":p+2,
                        "unsafe_session":False}
                       for d in dates for t,p in (("000001",100),("000002",200))])
    signals=pd.DataFrame({"date":[dates[0],dates[0]],"ticker":["000001","000002"],
                          "score":[.1,.2],"turnover":[2e9,2e9]})
    return dates,bars,signals


def test_entry_next_session_exit_fixed_and_cost():
    dates,bars,signals=inputs()
    a,r=simulate(bars,signals,dates,horizon=5,top_k=1,
                 initial_cash_krw=10000,ticket_krw=1000,assumed_roundtrip_bps=100)
    assert r["completed_trades"]==1
    assert a.entry_date.iloc[0]==dates[1]
    assert a.exit_date.iloc[0]==dates[5]
    assert a.net_trade_return.iloc[0] < a.gross_return.iloc[0]


def test_unfilled_selected_top_not_replaced_with_second():
    dates,bars,signals=inputs()
    bars.loc[bars.date.eq(dates[1])&bars.ticker.eq("000001"),"open"]=np.nan
    a,r=simulate(bars,signals,dates,horizon=5,top_k=1)
    assert len(a)==0
    assert r["skipped_reason_counts"]["unfilled_next_open"]==1


def test_missing_exit_requires_no_profit_claim():
    dates,bars,signals=inputs()
    bars.loc[bars.date.eq(dates[5])&bars.ticker.eq("000001"),"close"]=np.nan
    _,r=simulate(bars,signals,dates,horizon=5,top_k=1)
    assert r["status"].startswith("BLOCKED")
    assert r["net_return_only_if_all_resolved"] is None


def test_2026_holdout_is_locked():
    dates,bars,signals=inputs()
    with pytest.raises(ValueError,match="locked"):
        simulate(bars,signals,dates+pd.DateOffset(years=3),horizon=5)


def test_cash_position_constraint():
    dates,bars,signals=inputs()
    a,r=simulate(bars,signals,dates,horizon=5,top_k=2,max_positions=1,
                 initial_cash_krw=10000,ticket_krw=1000)
    assert len(a)==1
    assert r["skipped_reason_counts"]["position_limit_or_already_held"]==1


def test_intermediate_split_or_missing_bar_blocks_entire_pnl():
    dates,bars,signals=inputs()
    # Price is present at entry and exit but a split-like event happened between.
    bars.loc[bars.date.eq(dates[3])&bars.ticker.eq("000001"),
             "unsafe_session"]=True
    trades,report=simulate(bars,signals,dates,horizon=5,top_k=1)
    assert len(trades)==0
    assert report["status"].startswith("BLOCKED")
    assert report["net_return_only_if_all_resolved"] is None
    assert report["skipped_reason_counts"]["unresolved_intra_holding_bar_or_corporate_action"]==1



def test_marked_equity_captures_unrealized_drawdown_between_entry_and_exit():
    dates,bars,signals=inputs()
    # One held security falls before recovery; the original simulator only
    # recorded completed trade returns and could hide pathwise risk.
    bars.loc[bars.date.eq(dates[3])&bars.ticker.eq("000001"),"close"]=80.
    _,r=simulate(bars,signals,dates,horizon=5,top_k=1,
                 initial_cash_krw=10000,ticket_krw=1000,
                 assumed_roundtrip_bps=0)
    assert r["status"].startswith("HYPOTHETICAL")
    assert r["max_mark_to_market_drawdown_if_resolved"] < -.01
    assert r["worst_session_marked_nav_change_if_resolved"] < -.01


def test_unresolved_split_invalidates_nav_and_terminal_profit():
    dates,bars,signals=inputs()
    bars.loc[bars.date.eq(dates[4])&bars.ticker.eq("000001"),
             "unsafe_session"]=True
    _,r=simulate(bars,signals,dates,horizon=5,top_k=1,
                 initial_cash_krw=10000,ticket_krw=1000)
    assert r["status"].startswith("BLOCKED")
    assert r["max_mark_to_market_drawdown_if_resolved"] is None
    assert r["net_return_only_if_all_resolved"] is None
