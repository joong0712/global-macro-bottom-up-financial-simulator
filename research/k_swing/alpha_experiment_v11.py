"""Four frozen profit-first alpha-hypothesis tests, not verified investments.

Data 2017-2022 and signals 2019-2022 only. Reused historical windows
are not independent confirmation. No source OHLCV leaves private runners.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import pandas as pd
from .alpha_candidates_v11 import METHODS, build_candidates
from .data import load_calendar, validate_prices
from .vcr_experiment_v10 import sampled
from .vcr_execution_v10 import simulate_brackets

SPLITS = (
    ("discovery_2019_20", pd.Timestamp("2019-01-01"), pd.Timestamp("2020-12-15")),
    ("internal_2021_22", pd.Timestamp("2021-01-01"), pd.Timestamp("2022-12-15")),
)


def run(data_dir: Path, output_dir: Path, *, method: str, modulus: int = 16) -> dict:
    if method not in METHODS or modulus < 1:
        raise ValueError("Unknown predefined method or modulus")
    audit_path = data_dir / "market_structure_quality.json"
    if not audit_path.is_file():
        raise ValueError("Run historical quality audit first")
    audit = json.loads(audit_path.read_text(encoding="utf-8"))
    cal_report = audit.get("calendar", {})
    if cal_report.get("reference_only_dates") or cal_report.get("observed_only_dates"):
        raise ValueError("Unresolved KRX exchange calendar differences")
    private = data_dir / "_private"
    pieces = []
    for year in range(2017, 2023):
        path = private / f"kswing_screened_{year}.csv.gz"
        if not path.is_file():
            raise FileNotFoundError(f"Required screened history missing for {year}")
        for chunk in pd.read_csv(path, dtype={"ticker": "string"},
                                 parse_dates=["date"], chunksize=100_000):
            if "unsafe_session" not in chunk:
                raise ValueError("Unscreened market inputs are forbidden")
            selected = chunk.ticker.map(lambda code: sampled(code, modulus))
            if selected.any():
                pieces.append(chunk.loc[selected])
    if not pieces:
        raise ValueError("Empty historical deterministic security sample")
    bars = validate_prices(pd.concat(pieces, ignore_index=True))
    dates = load_calendar(private / "krx_observed_sessions.csv", bars)
    if dates.max().year > 2022 or bars.date.max().year > 2022:
        raise ValueError("2023-2026 holdouts locked")
    signals = build_candidates(bars, dates)
    selected = signals.loc[signals.strategy.eq(method),
                           ["date", "ticker", "score", "turnover"]].copy()
    scenarios = []
    for split, first, last in SPLITS:
        scoped = selected.loc[selected.date.ge(first) & selected.date.le(last)]
        for horizon in (5, 10):
            r = simulate_brackets(
                bars, scoped, dates, horizon=horizon, top_k=10,
                stop_pct=.03, take_pct=.08, initial_cash_krw=100_000_000,
                ticket_krw=5_000_000, max_positions=10,
                assumed_roundtrip_bps=50.)
            scenarios.append({"split": split, "horizon": horizon,
                              "raw_signals": len(scoped), **r})
    for horizon in (5, 10):
        tests = [r for r in scenarios if r["horizon"] == horizon]
        qualified = all(
            r["status"] == "HYPOTHETICAL_OHLC_ONLY"
            and r["completed_trades"] >= 30
            and r["hypothetical_net_return_if_resolved"] is not None
            and r["hypothetical_net_return_if_resolved"] > 0
            for r in tests)
        for r in tests:
            r["passes_predeclared_both_split_profit_gate"] = qualified
    result = {
        "status": "EXPLORATORY_PROFIT_FIRST_NOT_VERIFIED_PNL",
        "hypothesis": method,
        "sample_rule": f"sha256(ticker) % {modulus} == 0",
        "sampled_tickers": int(bars.ticker.nunique()),
        "training_only": True,
        "first_signal": "2019-01-01",
        "discovery_last_signal": "2020-12-15",
        "internal_last_signal": "2022-12-15",
        "2023_2026_holdouts_opened": False,
        "common_253_session_quality_and_liquidity_gate": True,
        "ticket_krw": 5_000_000,
        "initial_cash_krw": 100_000_000,
        "assumed_cost_roundtrip_bps": 50,
        "stop_pct": -.03, "take_pct": .08,
        "historical_securities_events_verified": False,
        "actual_broker_fills_and_taxes_verified": False,
        "scenarios": scenarios,
        "warning": ("Different strategy signal sets still create different account "
                    "exposure despite same initial capital. No legal-market-fill "
                    "or actual after-cost alpha conclusion. Reused history only."),
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / f"v11_{method}_aggregate.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"method": method, "status": result["status"],
                      "sampled_tickers": result["sampled_tickers"],
                      "scenarios": [{"split": r["split"], "h": r["horizon"],
                                     "signals": r["raw_signals"],
                                     "trades": r["completed_trades"],
                                     "status": r["status"],
                                     "account_return": r["hypothetical_net_return_if_resolved"]}
                                    for r in scenarios],
                      "holdouts_locked": True}), flush=True)
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--method", required=True, choices=METHODS)
    parser.add_argument("--data", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--modulus", type=int, default=16)
    args = parser.parse_args()
    run(args.data, args.output, method=args.method, modulus=args.modulus)


if __name__ == "__main__":
    main()
