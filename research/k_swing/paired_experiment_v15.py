"""Two independent, parallel matched-opportunity scientific diagnostics.

Important: matched isolated trade returns are NOT same as investable cash
portfolio returns. This study isolates exit effects of 2019-2022 reused
signals, and does not revisit locked 2023-2026 datasets.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

from .alpha_common_v12 import load_screened_sample
from .ichimoku_ma_timing_v13 import build_timing_candidates
from .paired_exit_v15 import paired_comparison, COST_BPS, BLOCK_SESSIONS

ENTRIES = ("ichi_ma_confirm", "vcr_trend_control")
PERIODS = (
    ("discovery_2019_20", pd.Timestamp("2019-01-01"), pd.Timestamp("2020-12-15")),
    ("development_2021_22", pd.Timestamp("2021-01-01"), pd.Timestamp("2022-12-15")),
)


def run(data_dir: Path, output_dir: Path, *,
        entry: str, modulus: int = 16) -> dict:
    if entry not in ENTRIES:
        raise ValueError("Frozen entry cohort only")
    bars, dates = load_screened_sample(data_dir, modulus)
    all_signals = build_timing_candidates(bars, dates)
    signals = all_signals.loc[
        all_signals.strategy.eq(entry), ["date", "ticker", "score", "turnover"]
    ]
    results = []
    for label, first, last in PERIODS:
        for hold in (5, 10):
            report = paired_comparison(
                bars, signals, dates, first=first, last=last,
                horizon=hold, seed=1837,
            )
            results.append({"split": label, "max_hold": hold, **report})

    # Independent confirmation has not occurred. A diagnostic "success"
    # requires positive net trade expectancy at BOTH assumed fee levels
    # 50bp/100bp and both reused periods, plus statistically positive
    # 20-calendar-day block CI for improvement over matched baseline.
    candidates = []
    for hold in (5, 10):
        for exit_mode in ("kijun_break", "sma20_break", "either_break"):
            tests = []
            for r in results:
                if r["max_hold"] != hold or r["status"] != (
                        "PAIRED_TRADE_DIAGNOSTIC_NOT_CAPITAL_PORTFOLIO"):
                    continue
                z = next(c for c in r["comparisons"]
                         if c["compared_exit"] == exit_mode)
                tests.append((r, z))
            passed = (len(tests) == 2 and
                      all(
                          r["completed_matched"] >= 30
                          and z["cost_50bps"]["variant_mean_net_trade"] > 0
                          and z["cost_100bps"]["variant_mean_net_trade"] > 0
                          and z["cost_50bps"]["paired_20session_block_ci95_lower"] is not None
                          and z["cost_50bps"]["paired_20session_block_ci95_lower"] > 0
                          for r, z in tests
                      ))
            candidates.append({
                "compared_exit": exit_mode, "max_hold": hold,
                "passes_reused_periods_diagnostic_gate": bool(passed),
            })

    output = {
        "project": "K-SWING v1.5 matched opportunity exit effect",
        "entry": entry,
        "status": "TRAINING_ERA_PAIRED_DIAGNOSTIC_NOT_VERIFIED_ALPHA",
        "periods": "2019-2020 and 2021-2022 previously inspected",
        "sampled_tickers": int(bars.ticker.nunique()),
        "samples_by_hash_modulus": modulus,
        "candidate_exit_methods": ["baseline", "kijun_break", "sma20_break", "either_break"],
        "entry_timing": "T+1 open all arms, no early peeking",
        "fixed_stop_take_pct": [-.03, .08],
        "cost_stress_roundtrip_bps": list(COST_BPS),
        "bootstrap_calendar_block_sessions": BLOCK_SESSIONS,
        "bootstrap_replications": 2000,
        "true_capital_account": False,
        "holdouts_2023_2026_opened": False,
        "official_issuer_actions_delistings_taxes_fills_verified": False,
        "results": results,
        "candidate_diagnostic_gates": candidates,
        "warning": (
            "Isolated same-entry gross-independent ticket results, not executable "
            "account PnL: ignores cash overlap, share rounding, stock lot constraints. "
            "Calendar block bootstrap is only diagnostic, not multiple-testing "
            "adjusted or truly independent confirmation. Never trade this study."
        ),
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / f"v15_{entry}_paired_aggregate.json"
    path.write_text(json.dumps(output, ensure_ascii=False, indent=2),
                    encoding="utf-8")
    print(json.dumps({
        "entry": entry, "status": output["status"],
        "sampled_tickers": output["sampled_tickers"],
        "results": [{
            "split": r["split"], "hold": r["max_hold"],
            "status": r["status"], "matched": r["completed_matched"],
            "comparisons": [{
                "exit": c["compared_exit"], "net50": c["cost_50bps"]["variant_mean_net_trade"],
                "delta50": c["cost_50bps"]["mean_matched_improvement"],
                "low95": c["cost_50bps"]["paired_20session_block_ci95_lower"],
                "high95": c["cost_50bps"]["paired_20session_block_ci95_upper"],
            } for c in r["comparisons"]],
        } for r in results],
        "holdouts_locked": True,
    }, ensure_ascii=False), flush=True)
    return output


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--data", required=True, type=Path)
    p.add_argument("--output", required=True, type=Path)
    p.add_argument("--entry", required=True, choices=ENTRIES)
    p.add_argument("--modulus", type=int, default=16)
    args = p.parse_args()
    run(args.data, args.output, entry=args.entry, modulus=args.modulus)


if __name__ == "__main__":
    main()
