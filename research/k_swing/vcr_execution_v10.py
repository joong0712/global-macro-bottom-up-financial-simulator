"""Conservative OHLC bracket simulation, not real KRX execution fills.

The stop-first rule only resolves unknown intraday sequencing pessimistically.
Unverified split, missing held bar, or delisting blocks the entire PnL claim.
"""
from __future__ import annotations

from collections import Counter, defaultdict
import numpy as np
import pandas as pd

from .vcr_strategy_v10 import _calendar


def simulate_brackets(bars: pd.DataFrame, signals: pd.DataFrame,
                      calendar: pd.DatetimeIndex, *, horizon: int = 10,
                      stop_pct: float = .03, take_pct: float = .08,
                      top_k: int = 10, initial_cash_krw: int = 100_000_000,
                      ticket_krw: int = 5_000_000, max_positions: int = 10,
                      assumed_roundtrip_bps: float = 50.,
                      entry_delay_sessions: int = 1,
                      max_signal_turnover_fraction: float = .005) -> dict:
    """Return aggregate-only engineering results. Never publish stock fill traces.

    T close score -> T+entry_delay opening print (no trade if unavailable). T+delay+H-1 last
    close, earlier stop/take based on held-session OHLC. At an overnight gap,
    use opening price, not a fictional stop fill. Intrabar both hit -> stop.
    """
    dates = _calendar(calendar)
    required_b = {"date", "ticker", "open", "high", "low", "close", "unsafe_session"}
    required_s = {"date", "ticker", "score", "turnover"}
    if not required_b.issubset(bars) or not required_s.issubset(signals):
        raise ValueError("Missing screened bars or signals")
    if (horizon < 1 or top_k < 1 or max_positions < 1 or initial_cash_krw <= 0
            or ticket_krw <= 0 or entry_delay_sessions not in (1, 2)
            or not (0 < stop_pct < 1) or take_pct <= 0
            or assumed_roundtrip_bps < 0 or not 0 < max_signal_turnover_fraction <= 1):
        raise ValueError("Invalid capital/exit/fee configuration")
    b, sig = bars.copy(), signals.copy()
    for frame in (b, sig):
        frame["date"] = pd.to_datetime(frame.date).dt.normalize()
        frame["ticker"] = frame.ticker.astype("string")
        if (frame.duplicated(["date", "ticker"]).any()
                or not frame.date.isin(dates).all()):
            raise ValueError("Duplicate/out-of-calendar stock-day")
    if not sig.empty and (sig[["score", "turnover"]].isna().any().any()
                          or not np.isfinite(sig.score.to_numpy(dtype=float)).all()):
        raise ValueError("Invalid score or liquidity at T")
    if b.unsafe_session.isna().any():
        raise ValueError("Unknown bar safety flag")
    indexed = {(r.date, str(r.ticker)): r for r in b.itertuples(index=False)}
    rank = {d: i for i, d in enumerate(dates)}
    signal_days = set(sig.date)
    queue = defaultdict(list)
    positions = {}
    half_fee = assumed_roundtrip_bps / 20000
    cash = float(initial_cash_krw)
    nav, missed, closed, exit_causes = [], Counter(), 0, Counter()
    blocked = False

    for day in dates:
        # Next opening print only; decisions known at prior session's close.
        for order in queue.pop(day, []):
            ticker = order["ticker"]
            if ticker in positions or len(positions) >= max_positions:
                missed["position_cap_or_held"] += 1
                continue
            bar = indexed.get((day, ticker))
            if (bar is None or bool(bar.unsafe_session)
                    or not np.isfinite(float(bar.open)) or bar.open <= 0):
                missed["no_next_open_print"] += 1
                continue
            price = float(bar.open)
            qty = int(ticket_krw // (price * (1 + half_fee)))
            if qty < 1:
                missed["too_expensive"] += 1
                continue
            debit = qty * price * (1 + half_fee)
            if debit > cash:
                missed["insufficient_cash"] += 1
                continue
            cash -= debit
            positions[ticker] = {"qty": qty, "entry": price,
                                 "last_day": order["last_day"]}
        # A safety flag/missing held bar blocks all terminal performance.
        for ticker, pos in list(positions.items()):
            bar = indexed.get((day, ticker))
            if (bar is None or bool(bar.unsafe_session)
                    or not all(np.isfinite(float(getattr(bar, k)))
                               for k in ("open", "high", "low", "close"))
                    or not (0 < bar.low <= min(bar.open, bar.close)
                            <= max(bar.open, bar.close) <= bar.high)):
                blocked = True
                missed["unresolved_holding_bar_or_corporate_action"] += 1
                del positions[ticker]
                continue
            entry = pos["entry"]
            stop, take = entry * (1 - stop_pct), entry * (1 + take_pct)
            reason, exit_price = None, None
            if bar.open <= stop:
                reason, exit_price = "gap_stop", float(bar.open)
            elif bar.open >= take:
                reason, exit_price = "gap_take", float(bar.open)
            elif bar.low <= stop:
                reason, exit_price = "intraday_stop_first", stop
            elif bar.high >= take:
                reason, exit_price = "intraday_take", take
            elif day == pos["last_day"]:
                reason, exit_price = "time_close", float(bar.close)
            if reason is not None:
                cash += pos["qty"] * exit_price * (1 - half_fee)
                exit_causes[reason] += 1
                closed += 1
                del positions[ticker]
        if not blocked:
            marked = cash
            for ticker, pos in positions.items():
                bar = indexed.get((day, ticker))
                if bar is None or bool(bar.unsafe_session) or not np.isfinite(float(bar.close)):
                    blocked = True
                    break
                marked += pos["qty"] * float(bar.close)
            if not blocked:
                nav.append(marked)
        if day not in signal_days:
            continue
        i = rank[day]
        if i + entry_delay_sessions + horizon - 1 >= len(dates):
            missed["insufficient_future_calendar_for_exit"] += 1
            continue
        candidates = sig.loc[sig.date.eq(day)].sort_values(
            ["score", "ticker"], kind="stable").head(top_k)
        for row in candidates.itertuples(index=False):
            if row.turnover < ticket_krw / max_signal_turnover_fraction:
                missed["signal_day_liquidity_fail"] += 1
                continue
            queue[dates[i + entry_delay_sessions]].append({"ticker": str(row.ticker),
                                         "last_day": dates[i + entry_delay_sessions + horizon - 1]})
    if positions or any(queue.values()):
        blocked = True
        missed["unfinished_position"] += len(positions)
    if blocked or not nav:
        net, mdd = None, None
    else:
        a = np.asarray(nav, dtype=float)
        peaks = np.maximum.accumulate(np.r_[float(initial_cash_krw), a])[1:]
        net = float(a[-1] / initial_cash_krw - 1)
        mdd = float((a / peaks - 1).min())
    return {
        "status": "BLOCKED_UNRESOLVED_POSITION" if blocked else "HYPOTHETICAL_OHLC_ONLY",
        "completed_trades": closed,
        "entry_delay_sessions": entry_delay_sessions,
        "assumed_roundtrip_bps": assumed_roundtrip_bps,
        "hypothetical_net_return_if_resolved": net,
        "hypothetical_marked_mdd_if_resolved": mdd,
        "exit_causes": dict(exit_causes), "skip_reasons": dict(missed),
        "conservative_both_hit_stop_first": True,
        "official_security_events_verified": False,
        "historical_broker_fees_taxes_verified": False,
        "opening_auction_and_stop_fills_verified": False,
        "2023_2026_holdouts_opened": False,
    }
