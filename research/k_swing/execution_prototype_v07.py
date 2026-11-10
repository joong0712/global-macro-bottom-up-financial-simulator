"""Hypothetical T+1-open / T+H-close cash ledger; NOT verified fills or net alpha.

At T close selection depends only on score and T turnover. At next open
we may fail to fill; no replacement by the next profitable security. Unknown
exit (suspension/delisting) blocks the entire performance claim. All broker
fees/taxes/slippage are EXPLICIT hypothetical bps scenarios.
"""
from __future__ import annotations

from collections import defaultdict
import numpy as np
import pandas as pd


def simulate(bars: pd.DataFrame, signals: pd.DataFrame,
             calendar: pd.DatetimeIndex, *,
             horizon: int = 10, top_k: int = 10,
             initial_cash_krw: int = 100_000_000,
             ticket_krw: int = 5_000_000,
             max_positions: int = 10,
             assumed_roundtrip_bps: float = 50.,
             max_signal_turnover_fraction: float = .005):
    """Return (PRIVATE fill trace, public-safe aggregate summary).

    bars: date, ticker, open, close, unsafe_session
    signals: date, ticker, score, turnover. Score known at T close.
    """
    if not {"date","ticker","open","close","unsafe_session"}.issubset(bars):
        raise ValueError("missing bar fields")
    if not {"date","ticker","score","turnover"}.issubset(signals):
        raise ValueError("missing signal fields")
    if horizon<1 or top_k<1 or max_positions<1 or initial_cash_krw<=0 or ticket_krw<=0:
        raise ValueError("invalid capital or holding rules")
    if assumed_roundtrip_bps<0 or not 0<max_signal_turnover_fraction<=1:
        raise ValueError("invalid cost or turnover rule")
    dates=pd.DatetimeIndex(calendar).normalize()
    if dates.has_duplicates or not dates.is_monotonic_increasing or len(dates)<horizon+2:
        raise ValueError("unique sorted observed exchange sessions required")
    if (dates.year>=2024).any():
        raise ValueError("2024-26 holdouts are locked")
    b,s=bars.copy(),signals.copy()
    for frame in (b,s):
        frame["date"]=pd.to_datetime(frame.date).dt.normalize()
        frame["ticker"]=frame.ticker.astype("string")
    if b.duplicated(["date","ticker"]).any() or s.duplicated(["date","ticker"]).any():
        raise ValueError("duplicate security/session")
    if not b.date.isin(dates).all() or not s.date.isin(dates).all():
        raise ValueError("out of calendar")
    if s[["score","turnover"]].isna().any().any():
        raise ValueError("unknown signal at T")
    bar_index={(r.date,str(r.ticker)):r for r in b.itertuples(index=False)}
    ranks={date:idx for idx,date in enumerate(dates)}
    pending=defaultdict(list)
    positions={}
    fee=assumed_roundtrip_bps/20000
    cash=float(initial_cash_krw)
    records=[]
    nav_marks=[]  # PRIVATE per-session mark-to-market, never a public price series.
    missed=defaultdict(int)
    unresolved=False
    seen_signal_dates=set(s.date)
    for date in dates:
        # At session open: only candidates selected on previous session.
        for order in pending.pop(date,[]):
            ticker=order["ticker"]
            if ticker in positions or len(positions)>=max_positions:
                missed["position_limit_or_already_held"]+=1
                continue
            if cash<ticket_krw*(1+fee):
                missed["insufficient_cash"]+=1
                continue
            bar=bar_index.get((date,ticker))
            if bar is None or bool(bar.unsafe_session) or pd.isna(bar.open) or float(bar.open)<=0:
                missed["unfilled_next_open"]+=1
                continue
            price=float(bar.open)
            qty=int(ticket_krw//price)
            if qty<1:
                missed["too_expensive_for_ticket"]+=1
                continue
            gross=qty*price
            debit=gross*(1+fee)
            if debit>cash:
                missed["insufficient_cash"]+=1
                continue
            cash-=debit
            positions[ticker]={**order,"entry_date":date,"entry_price":price,
                               "qty":qty,"debit":debit}
        # Intermediate bar gaps and suspected corporate actions can make a held
        # position unpriceable. NEVER carry it through and book a fictional exit.
        for ticker,pos in list(positions.items()):
            bar=bar_index.get((date,ticker))
            if bar is None or bool(bar.unsafe_session) or pd.isna(bar.close) or float(bar.close)<=0:
                unresolved=True
                missed["unresolved_intra_holding_bar_or_corporate_action"]+=1
                del positions[ticker]
        # At session close: exits scheduled using original signal date.
        for ticker,pos in list(positions.items()):
            if pos["exit_date"]!=date:
                continue
            bar=bar_index.get((date,ticker))
            if bar is None or bool(bar.unsafe_session) or pd.isna(bar.close) or float(bar.close)<=0:
                unresolved=True
                missed["unresolved_exit_delist_or_suspension"]+=1
                del positions[ticker]
                continue
            close=float(bar.close)
            proceeds=pos["qty"]*close*(1-fee)
            cash+=proceeds
            records.append({
                "ticker":ticker,"signal_date":pos["signal_date"],
                "entry_date":pos["entry_date"],"exit_date":date,
                "gross_return":close/pos["entry_price"]-1,
                "net_cash_pnl_krw":proceeds-pos["debit"],
                "net_trade_return":proceeds/pos["debit"]-1,
            })
            del positions[ticker]
        # Mark the whole cash + held-share account at each session close,
        # including temporary unrealized drawdowns between entry and exit.
        # Do not claim any equity path after a missing/delisted position.
        if not unresolved:
            value=cash
            for held_ticker,held in positions.items():
                close_bar=bar_index.get((date,held_ticker))
                if close_bar is None or bool(close_bar.unsafe_session) or pd.isna(close_bar.close):
                    unresolved=True
                    missed["missing_mark_to_market_close"]+=1
                    break
                value+=held["qty"]*float(close_bar.close)
            if not unresolved:
                nav_marks.append(float(value))
        if date not in seen_signal_dates:
            continue
        # At T close, rank without forward returns or future trade availability.
        t=ranks[date]
        if t+horizon>=len(dates):
            missed["future_exit_outside_input"]+=1
            continue
        choices=s.loc[s.date.eq(date)].sort_values(["score","ticker"],kind="stable").head(top_k)
        for row in choices.itertuples(index=False):
            if not np.isfinite(float(row.score)) or float(row.turnover)<ticket_krw/max_signal_turnover_fraction:
                missed["known_signal_liquidity_fail"]+=1
                continue
            pending[dates[t+1]].append({
                "ticker":str(row.ticker),"signal_date":date,
                "exit_date":dates[t+horizon],"score_known_T":float(row.score)
            })
    if positions or any(pending.values()):
        unresolved=True
        missed["unfinished_positions"]+=len(positions)
    if not unresolved and nav_marks:
        marks=np.asarray(nav_marks,float)
        prev=np.r_[float(initial_cash_krw),marks[:-1]]
        peaks=np.maximum.accumulate(np.r_[float(initial_cash_krw),marks])[1:]
        mdd=float((marks/peaks-1).min())
        worst_daily=float((marks/prev-1).min())
        max_marked_equity=float(marks.max())
    else:
        mdd=worst_daily=max_marked_equity=None
    summary={
        "status":("HYPOTHETICAL_OPEN_CLOSE_PRINTS_ONLY" if not unresolved else
                  "BLOCKED_UNRESOLVED_EXIT_OR_DELISTING"),
        "completed_trades":len(records),
        "starting_cash":initial_cash_krw,
        "end_cash_only_if_all_resolved":cash if not unresolved else None,
        "net_return_only_if_all_resolved":cash/initial_cash_krw-1 if not unresolved else None,
        "assumed_roundtrip_bps":assumed_roundtrip_bps,
        "max_mark_to_market_drawdown_if_resolved":mdd,
        "worst_session_marked_nav_change_if_resolved":worst_daily,
        "max_marked_equity_if_resolved":max_marked_equity,
        "marks_are_unadjusted_close_prints_not_executable":True,
        "skipped_reason_counts":dict(missed),
        "actual_broker_fees_taxes_verified":False,
        "open_close_auction_fills_verified":False,
        "security_actions_and_delistings_verified":False,
        "2026_holdout_touched":False,
        "warning":"Historical close prints are not guaranteed fills, official transaction taxes not applied; unresolved exits never assumed to be a free trade."
    }
    return pd.DataFrame(records),summary
