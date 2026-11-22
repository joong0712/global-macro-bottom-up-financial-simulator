"""Parallel, predeclared Ichimoku/SMA exit experiments on two entry families.

Research uses already-explored 2019-2022 and distinct cash books;
neither period supplies fresh independent evidence. No 2023-2026 bars.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

from .alpha_common_v12 import load_screened_sample
from .ichimoku_ma_timing_v13 import build_timing_candidates
from .ichimoku_ma_exit_v14 import EXIT_MODES, simulate_exit_policy

ENTRIES = ("ichi_ma_confirm", "vcr_trend_control")
SPLITS = (
    ("discovery_2019_20", pd.Timestamp("2019-01-01"), pd.Timestamp("2020-12-15")),
    ("development_2021_22", pd.Timestamp("2021-01-01"), pd.Timestamp("2022-12-15")),
)


def run(data_dir: Path, output_dir: Path, *, entry: str, exit_mode: str,
        modulus: int = 16) -> dict:
    if entry not in ENTRIES or exit_mode not in EXIT_MODES:
        raise ValueError("Predeclared entry and exit rule required")
    bars, dates = load_screened_sample(data_dir, modulus)
    all_signals = build_timing_candidates(bars, dates)
    selected = all_signals.loc[
        all_signals.strategy.eq(entry), ["date", "ticker", "score", "turnover"]
    ]
    results = []
    for split, first, last in SPLITS:
        scoped = selected.loc[selected.date.between(first, last)]
        for horizon in (5, 10):
            final_signal_idx = dates.searchsorted(last, side="right") - 1
            exposure_end = dates[min(final_signal_idx + horizon, len(dates) - 1)]
            r = simulate_exit_policy(
                bars, scoped, dates,
                exit_mode=exit_mode, horizon=horizon,
                exposure_window_start=first,
                exposure_window_end=exposure_end,
                initial_cash_krw=100_000_000,
                ticket_krw=5_000_000, max_positions=10,
                top_k=10, stop_pct=.03, take_pct=.08,
                assumed_roundtrip_bps=50.,
            )
            results.append({
                "split": split, "horizon": horizon,
                "signal_count": int(len(scoped)), **r,
            })
    # Any single invalid held print/issuer action disqualifies the *entire*
    # arm from a real PnL claim. No loss can be silently discarded.
    for horizon in (5, 10):
        case = [r for r in results if r["horizon"] == horizon]
        passed = all(
            r["status"] == "HYPOTHETICAL_OHLC_ONLY"
            and r["completed_trades"] >= 30
            and r["hypothetical_net_return_if_resolved"] is not None
            and r["hypothetical_net_return_if_resolved"] > 0
            for r in case
        )
        for r in case:
            r["passes_both_reused_periods_profit_gate"] = passed
    output = {
        "project": "K-SWING v1.4 paper-grounded exits",
        "entry": entry, "exit_mode": exit_mode,
        "status": "RESEARCH_REUSED_HISTORY_NOT_VALIDATED_ALPHA",
        "source": "2017-2022 screened Korean equities, 1/16 hashed ticker sample",
        "signal_periods": "2019-2020 and 2021-2022, already inspected",
        "entry": entry,
        "buy": "T+1 market open only, if historically eligible",
        "sell": "T+1 open following T-close Kijun26/SMA20 breach, OR -3/+8 stop/take or H=5/10 time exit",
        "cash_krw": 100_000_000,
        "ticket_krw": 5_000_000, "max_positions": 10,
        "roundtrip_bps_assumed": 50,
        "data_2023_2026_accessed": False,
        "corporate_actions_delisting_fills_taxes_verified": False,
        "sampled_tickers": int(bars.ticker.nunique()),
        "results": results,
        "warning": ("Not an exposure-matched OOS portfolio. "
                    "No official corporate action/delisting mapping, real fills or actual taxes. "
                    "Real trading prohibited."),
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    file = output_dir / f"v14_{entry}_{exit_mode}_aggregate.json"
    file.write_text(json.dumps(output, ensure_ascii=False, indent=2),
                    encoding="utf-8")
    print(json.dumps({
        "entry": entry, "exit": exit_mode, "sampled_tickers": output["sampled_tickers"],
        "results": [{
            "split": r["split"], "h": r["horizon"],
            "signals": r["signal_count"], "trades": r["completed_trades"],
            "status": r["status"],
            "net_return": r["hypothetical_net_return_if_resolved"],
            "mdd": r["hypothetical_marked_mdd_if_resolved"],
            "mean_exposure": r["mean_daily_invested_fraction_if_resolved"],
            "mean_trade_net": r["mean_trade_net_return_if_resolved"],
            "exit_causes": r["exit_causes"],
        } for r in results], "2023_2026_holdouts_locked": True,
    }, ensure_ascii=False), flush=True)
    return output


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--data", required=True, type=Path)
    p.add_argument("--output", required=True, type=Path)
    p.add_argument("--entry", choices=ENTRIES, required=True)
    p.add_argument("--exit", dest="exit_mode", choices=EXIT_MODES, required=True)
    p.add_argument("--modulus", type=int, default=16)
    args = p.parse_args()
    run(args.data, args.output, entry=args.entry, exit_mode=args.exit_mode,
        modulus=args.modulus)


if __name__ == "__main__":
    main()
