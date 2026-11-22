"""Causal T-close exit signals and conservative T+1-open liquidation.

Only two indicator families: 9/26/52 Ichimoku and SMA 5/20/60.
No next-bar price is used to decide whether to exit. No stock-level data
or fill traces are returned by this research-only simulator.
"""
from __future__ import annotations

from collections import Counter, defaultdict

import numpy as np
import pandas as pd

from .ichimoku_ma_timing_v13 import indicator_frame
from .vcr_strategy_v10 import _calendar

EXIT_MODES = ("baseline", "kijun_break", "sma20_break", "either_break")


def exit_flags(bars: pd.DataFrame, calendar: pd.DatetimeIndex,
               method: str) -> set[tuple[pd.Timestamp, str]]:
    """Set of T-close exit instructions, executable no earlier than T+1 open."""
    dates = _calendar(calendar)
    if method not in EXIT_MODES:
        raise ValueError("Unknown frozen exit method")
    if method == "baseline":
        return set()
    flags = set()
    for ticker, group in bars.groupby("ticker", sort=True):
        f = indicator_frame(group, dates)
        kij = f.close.lt(f.kijun)
        sma = f.close.lt(f.sma20)
        signal = {"kijun_break": kij, "sma20_break": sma,
                  "either_break": (kij | sma)}[method]
        signal = signal & f.close.notna() & f.kijun.notna() & f.sma20.notna()
        flags.update((day, str(ticker)) for day in dates[signal.to_numpy()])
    return flags


def simulate_exit_policy(
    bars: pd.DataFrame, signals: pd.DataFrame, calendar: pd.DatetimeIndex, *,
    exit_mode: str, horizon: int = 5, initial_cash_krw: int = 100_000_000,
    ticket_krw: int = 5_000_000, max_positions: int = 10,
    top_k: int = 10, stop_pct: float = .03, take_pct: float = .08,
    assumed_roundtrip_bps: float = 50.,
    max_signal_turnover_fraction: float = .005,
) -> dict:
    """OHLC cash ledger with same entry/stop/take rules as v1.3.

    The optional indicator close-breach signal is observed after T close,
    then executed at the T+1 open if the position survives all T events.
    T+1 bar safety is checked before any liquidation. Result blocked if
    even one held bar cannot be verified; no selective removal of losses.
    """
    dates = _calendar(calendar)
    if exit_mode not in EXIT_MODES or horizon not in (5, 10):
        raise ValueError("Exit rule and holding periods must be preregistered")
    if not (0 < stop_pct < 1 and take_pct > 0 and top_k >= 1
            and 0 < max_signal_turnover_fraction <= 1
            and assumed_roundtrip_bps >= 0 and initial_cash_krw > 0
            and max_positions >= 1 and ticket_krw > 0):
        raise ValueError("Invalid fixed execution parameters")
    required_b = {"date", "ticker", "open", "high", "low", "close",
                  "volume", "turnover", "unsafe_session"}
    required_s = {"date", "ticker", "score", "turnover"}
    if not required_b.issubset(bars) or not required_s.issubset(signals):
        raise ValueError("Complete screened stock bars and T signals required")
    b, sig = bars.copy(), signals.copy()
    for data in (b, sig):
        data["date"] = pd.to_datetime(data.date).dt.normalize()
        data["ticker"] = data.ticker.astype("string")
        if data.duplicated(["date", "ticker"]).any() or not data.date.isin(dates).all():
            raise ValueError("Invalid or duplicate stock-day")
    if b.unsafe_session.isna().any() or not b.unsafe_session.isin([True, False]).all():
        raise ValueError("Unknown held security action")
    if len(sig) and (sig[["score", "turnover"]].isna().any().any()
                     or not np.isfinite(sig.score.to_numpy(dtype=float)).all()):
        raise ValueError("Invalid T-close score")

    idx = {(r.date, str(r.ticker)): r for r in b.itertuples(index=False)}
    rank = {date: i for i, date in enumerate(dates)}
    instructions = exit_flags(b, dates, exit_mode)
    queue = defaultdict(list)
    pending_indicator_exits = set()
    positions = {}
    cash = float(initial_cash_krw)
    half_fee = assumed_roundtrip_bps / 20000
    nav, daily_exposures, closed_returns = [], [], []
    reasons, skipped = Counter(), Counter()
    blocked = False
    realized_buy_notional = 0.
    realized_sale_notional = 0.

    def checked_bar(day, ticker):
        bar = idx.get((day, ticker))
        if bar is None or bool(bar.unsafe_session):
            return None
        if not all(np.isfinite(float(getattr(bar, k)))
                   for k in ("open", "high", "low", "close")):
            return None
        if not (0 < bar.low <= min(bar.open, bar.close)
                <= max(bar.open, bar.close) <= bar.high):
            return None
        return bar

    def close_position(ticker, price, reason):
        nonlocal cash, realized_sale_notional
        pos = positions.pop(ticker)
        proceeds = pos["qty"] * float(price) * (1 - half_fee)
        cash += proceeds
        realized_sale_notional += pos["qty"] * float(price)
        closed_returns.append(proceeds / pos["entry_cost"] - 1)
        reasons[reason] += 1

    for day in dates:
        # Exit orders from yesterday's market close execute FIRST this morning.
        # The previous-day trigger does not see today's open or high/low.
        for ticker in sorted(pending_indicator_exits):
            if ticker not in positions:
                continue
            bar = checked_bar(day, ticker)
            if bar is None:
                blocked = True
                skipped["unresolved_holding_bar_or_corporate_action"] += 1
                del positions[ticker]
                continue
            close_position(ticker, float(bar.open), "next_open_indicator_exit")
        pending_indicator_exits.clear()

        for order in queue.pop(day, []):
            ticker = order["ticker"]
            if ticker in positions or len(positions) >= max_positions:
                skipped["position_cap_or_held"] += 1
                continue
            bar = checked_bar(day, ticker)
            if bar is None:
                skipped["no_valid_entry_open"] += 1
                continue
            price = float(bar.open)
            qty = int(ticket_krw // (price * (1 + half_fee)))
            if qty <= 0:
                skipped["price_exceeds_ticket"] += 1
                continue
            debit = qty * price * (1 + half_fee)
            if debit > cash:
                skipped["insufficient_cash"] += 1
                continue
            cash -= debit
            realized_buy_notional += qty * price
            positions[ticker] = {
                "qty": qty, "entry": price, "entry_cost": debit,
                "last_day": order["last_day"],
            }

        for ticker, pos in list(positions.items()):
            bar = checked_bar(day, ticker)
            if bar is None:
                blocked = True
                skipped["unresolved_holding_bar_or_corporate_action"] += 1
                del positions[ticker]
                continue
            stop = pos["entry"] * (1 - stop_pct)
            take = pos["entry"] * (1 + take_pct)
            reason, price = None, None
            if bar.open <= stop:
                reason, price = "gap_stop", float(bar.open)
            elif bar.open >= take:
                reason, price = "gap_take", float(bar.open)
            elif bar.low <= stop:
                reason, price = "intraday_stop_first", stop
            elif bar.high >= take:
                reason, price = "intraday_take", take
            elif day == pos["last_day"]:
                reason, price = "time_close", float(bar.close)
            if reason is not None:
                close_position(ticker, price, reason)
            elif (day, ticker) in instructions:
                pending_indicator_exits.add(ticker)

        if not blocked:
            exposure_value = 0.
            for ticker, pos in positions.items():
                bar = checked_bar(day, ticker)
                if bar is None:
                    blocked = True
                    skipped["unresolved_mark_to_market"] += 1
                    break
                exposure_value += pos["qty"] * float(bar.close)
            if not blocked:
                account_nav = cash + exposure_value
                nav.append(account_nav)
                daily_exposures.append(
                    exposure_value / account_nav if account_nav > 0 else np.nan
                )

        if day not in set(sig.date):
            continue
        i = rank[day]
        if i + horizon >= len(dates):
            skipped["insufficient_future_calendar"] += 1
            continue
        ranked = sig.loc[sig.date.eq(day)].sort_values(
            ["score", "ticker"], kind="stable").head(top_k)
        for row in ranked.itertuples(index=False):
            if row.turnover < ticket_krw / max_signal_turnover_fraction:
                skipped["signal_turnover_fail"] += 1
                continue
            queue[dates[i + 1]].append({
                "ticker": str(row.ticker), "last_day": dates[i + horizon]
            })

    if positions or pending_indicator_exits or any(queue.values()):
        blocked = True
        skipped["unresolved_last_calendar_position"] += len(positions)
    if blocked or not nav:
        net_return, mdd, mean_exposure, mean_trade_return = (None,) * 4
    else:
        a = np.asarray(nav, dtype=float)
        peaks = np.maximum.accumulate(np.r_[float(initial_cash_krw), a])[1:]
        net_return = float(a[-1] / initial_cash_krw - 1)
        mdd = float((a / peaks - 1).min())
        mean_exposure = float(np.mean(daily_exposures))
        mean_trade_return = (float(np.mean(closed_returns))
                             if closed_returns else None)

    return {
        "status": "BLOCKED_UNRESOLVED_POSITION" if blocked else "HYPOTHETICAL_OHLC_ONLY",
        "completed_trades": len(closed_returns),
        "hypothetical_net_return_if_resolved": net_return,
        "hypothetical_marked_mdd_if_resolved": mdd,
        "mean_daily_invested_fraction_if_resolved": mean_exposure,
        "mean_trade_net_return_if_resolved": mean_trade_return,
        "realized_buy_notional_krw": realized_buy_notional,
        "realized_sale_notional_krw": realized_sale_notional,
        "exit_causes": dict(reasons),
        "skip_reasons": dict(skipped),
        "exit_trigger_only_at_T_close_executed_next_open": True,
        "stop_first_ambiguous_OHLC": True,
        "official_security_actions_and_delistings_verified": False,
        "actual_fills_taxes_verified": False,
        "2023_2026_holdouts_opened": False,
    }
