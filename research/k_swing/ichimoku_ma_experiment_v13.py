"""Parallel preregistered Korean Ichimoku / moving-average entry timing study.

Exploratory 2019-2022 research only. Same capital, exits, costs & screened
stock universe in all six strategy arms. T-close -> T+1 / T+2 opening prints.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

from .alpha_common_v12 import load_screened_sample
from .ichimoku_ma_timing_v13 import METHODS, build_timing_candidates
from .vcr_execution_v10 import simulate_brackets

SPLITS = (
    ("discovery_2019_20", pd.Timestamp("2019-01-01"), pd.Timestamp("2020-12-15")),
    ("development_2021_22", pd.Timestamp("2021-01-01"), pd.Timestamp("2022-12-15")),
)
HORIZONS = (5, 10)
DELAYS = (1, 2)


def run(data_dir: Path, output_dir: Path, *, method: str,
        modulus: int = 16) -> dict:
    if method not in METHODS:
        raise ValueError("Predeclared method required")
    bars, dates = load_screened_sample(data_dir, modulus)
    signals = build_timing_candidates(bars, dates)
    single = signals.loc[signals.strategy.eq(method),
                         ["date", "ticker", "score", "turnover"]]
    results = []
    for label, first, last in SPLITS:
        selected = single.loc[single.date.between(first, last)]
        for delay in DELAYS:
            for hold in HORIZONS:
                output = simulate_brackets(
                    bars, selected, dates,
                    horizon=hold, entry_delay_sessions=delay,
                    top_k=10, stop_pct=.03, take_pct=.08,
                    initial_cash_krw=100_000_000, ticket_krw=5_000_000,
                    max_positions=10, assumed_roundtrip_bps=50.,
                )
                results.append({
                    "split": label, "entry_delay_sessions": delay,
                    "max_holding_sessions": hold, "n_raw_signals": len(selected),
                    **output,
                })
    # This historical window was inspected in previous research;
    # a profitable simulation is only a hypothesis worth further study.
    for delay in DELAYS:
        for hold in HORIZONS:
            group = [r for r in results if r["entry_delay_sessions"] == delay
                     and r["max_holding_sessions"] == hold]
            eligible = all(
                x["status"] == "HYPOTHETICAL_OHLC_ONLY"
                and x["hypothetical_net_return_if_resolved"] is not None
                and x["hypothetical_net_return_if_resolved"] > 0
                and x["completed_trades"] >= 30 for x in group
            )
            for r in group:
                r["passes_profit_gate_in_both_exploratory_splits"] = eligible
    result = {
        "project": "K-SWING v1.3 ichimoku-and-MA-timing",
        "method": method,
        "status": "EXPLORATORY_NO_VERIFIED_REAL_PNL",
        "sample_rule": f"sha256(ticker) % {modulus} == 0",
        "sampled_tickers": int(bars.ticker.nunique()),
        "signal_years": "2019-2022, already inspected history, not new holdout",
        "indicators": "Ichimoku Tenkan 9/Kijun 26/Senkou B 52, cloud visibly delayed by 26, SMA 5/20/60",
        "enter_at": "T+1 or T+2 actual daily opening print; fixed wait, no intervening info selection",
        "exit": "fixed -3% stop/+8% take, stop-first OHLC sequencing or T+5/T+10 holding horizon",
        "cash_krw": 100_000_000,
        "ticket_krw": 5_000_000,
        "max_positions": 10,
        "roundtrip_cost_bps_assumed": 50,
        "price_history_from_2023_to_2026_opened": False,
        "company_actions_delistings_fills_and_taxes_certified": False,
        "results": results,
        "warning": ("Research signals on a tiny historical stock sample, no official "
                    "corporate-action/delisting or executed tax/slippage proof. "
                    "Holdout 2023-2026 locked. Live trading prohibited."),
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / f"v13_{method}_aggregate.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({
        "method": method, "sampled_tickers": result["sampled_tickers"],
        "scenarios": [{
            "split": r["split"], "entry_delay": r["entry_delay_sessions"],
            "hold": r["max_holding_sessions"], "signals": r["n_raw_signals"],
            "closed": r["completed_trades"], "status": r["status"],
            "net": r["hypothetical_net_return_if_resolved"],
            "mdd": r["hypothetical_marked_mdd_if_resolved"],
        } for r in results],
        "holdouts_locked": True,
    }, ensure_ascii=False), flush=True)
    return result


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--data", required=True, type=Path)
    p.add_argument("--output", required=True, type=Path)
    p.add_argument("--method", required=True, choices=METHODS)
    p.add_argument("--modulus", type=int, default=16)
    args = p.parse_args()
    run(args.data, args.output, method=args.method, modulus=args.modulus)


if __name__ == "__main__":
    main()
