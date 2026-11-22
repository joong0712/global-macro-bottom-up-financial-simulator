"""Private, training-era only engineering check for three predeclared VCR variants.

Never exports ticker/date/order data. Never labels a strategy profitable or live.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import pandas as pd

from .data import load_calendar, validate_prices
from .vcr_strategy_v10 import VCRConfig, STRATEGIES, build_signals
from .vcr_execution_v10 import simulate_brackets


def sampled(ticker: str, modulus: int) -> bool:
    return int.from_bytes(hashlib.sha256(str(ticker).encode("ascii")).digest()[:4], "big") % modulus == 0


def run(data_dir: Path, output_dir: Path, *, modulus: int = 16,
        cfg: VCRConfig = VCRConfig()) -> dict:
    if modulus < 1:
        raise ValueError("Invalid modulus")
    audit_path = data_dir / "market_structure_quality.json"
    if not audit_path.is_file():
        raise ValueError("Required historical quality audit missing")
    audit = json.loads(audit_path.read_text(encoding="utf-8"))
    cal_result = audit.get("calendar", {})
    if cal_result.get("reference_only_dates") or cal_result.get("observed_only_dates"):
        raise ValueError("Unresolved exchange calendar discrepancies")
    private = data_dir / "_private"
    pieces = []
    for year in range(2017, 2023):
        path = private / f"kswing_screened_{year}.csv.gz"
        if not path.is_file():
            raise FileNotFoundError(f"Screened private input missing: {year}")
        for chunk in pd.read_csv(path, dtype={"ticker": "string"},
                                 parse_dates=["date"], chunksize=100_000):
            if "unsafe_session" not in chunk:
                raise ValueError("Unscreened source not permitted")
            chosen = chunk.ticker.map(lambda code: sampled(code, modulus))
            if chosen.any():
                pieces.append(chunk.loc[chosen])
    if not pieces:
        raise ValueError("No sampled research securities")
    bars = validate_prices(pd.concat(pieces, ignore_index=True))
    sessions = load_calendar(private / "krx_observed_sessions.csv", bars)
    if sessions.max().year > 2022 or bars.date.max().year > 2022:
        raise ValueError("2023-2026 holdouts locked")
    signals = build_signals(bars, sessions, cfg)
    results = []
    for name in STRATEGIES:
        selected = signals.loc[signals.strategy.eq(name),
                               ["date", "ticker", "score", "turnover"]]
        for horizon in (5, 10):
            out = simulate_brackets(bars, selected, sessions, horizon=horizon,
                                    stop_pct=.03, take_pct=.08, top_k=10,
                                    initial_cash_krw=100_000_000,
                                    ticket_krw=5_000_000,
                                    assumed_roundtrip_bps=50.)
            results.append({"strategy": name, "horizon": horizon,
                            "n_raw_signals": len(selected), **out})
    # Aggregates are descriptive training-era engineering, not evidence of alpha.
    meta = {
        "status": "TRAINING_ERA_ENGINEERING_ONLY_NOT_VERIFIED_PNL",
        "period": "2017-2022 inputs; 2019-2022 signals only",
        "source_ticker_hash_modulus": modulus,
        "sampled_security_count": int(bars.ticker.nunique()),
        "params": cfg.__dict__,
        "exit_rules": {"stop": -0.03, "take": 0.08, "max_horizons": [5, 10],
                       "intrabar_both_hit": "stop_first",
                       "overnight_gaps": "use_actual_open_print"},
        "results": results,
        "2023_2026_holdouts_opened": False,
        "official_actions_and_delistings_verified": False,
        "actual_brokerage_fills_or_taxes_verified": False,
        "note": "Historical sample is pre-inspected. Never choose winner from these exploratory results; no live trades.",
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "vcr_v10_aggregate_only.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"status": meta["status"],
                      "strategies": list(STRATEGIES),
                      "scenarios": len(results),
                      "signals": {s: sum(r["n_raw_signals"] for r in results
                                     if r["strategy"] == s) // 2 for s in STRATEGIES},
                      "holdouts_locked": True}))
    return meta


def main():
    p = argparse.ArgumentParser(description="VCR training-only exploratory bracket study")
    p.add_argument("--data", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--modulus", type=int, default=16)
    args = p.parse_args()
    run(args.data, args.output, modulus=args.modulus)


if __name__ == "__main__":
    main()
