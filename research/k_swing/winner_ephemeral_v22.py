"""Run 2019-22 winner profiles using ephemeral 2017-22 screened marcap input.

Produces aggregate summaries only, never uploads raw prices or ticker rows.
This is provisional non-official data, NOT independently certified PnL.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import pandas as pd
from .factor_matrix_v04 import one_symbol_matrix
from .factor_pilot_v04 import is_sampled
from .winner_profiles_v20 import profile, summarize
from .winner_pairs_v21 import describe_pairs, consistency

def run(root: Path, output: Path, modulus: int = 16):
    if modulus < 1:
        raise ValueError("Invalid sample modulus")
    private = root / "_private"
    frames = []
    for year in range(2017, 2023):
        f = private / f"kswing_screened_{year}.csv.gz"
        if not f.is_file():
            raise FileNotFoundError(f"Missing screened year {year}")
        chunks = pd.read_csv(f, dtype={"ticker": "string"},
                             parse_dates=["date"], chunksize=100_000)
        for chunk in chunks:
            sub = chunk.loc[chunk.ticker.map(lambda x: is_sampled(x, modulus))]
            if not sub.empty:
                frames.append(sub)
    if not frames:
        raise ValueError("Empty selected sample")
    prices = pd.concat(frames, ignore_index=True)
    if prices.duplicated(["date", "ticker"]).any():
        raise ValueError("Duplicate price records")
    calendar = pd.DatetimeIndex(pd.to_datetime(
        pd.read_csv(private / "krx_observed_sessions.csv")["date"]))
    # The 2017-22 calendar has no 2026 rows; do not use 2023-26 prices.
    panels = []
    for ticker, bars in prices.groupby("ticker", sort=True):
        panels.append(one_symbol_matrix(
            bars, calendar, "2019-01-01", "2022-12-31"))
    panel = pd.concat(panels, ignore_index=True)
    single = pd.concat([profile(panel, horizon=h, rise_threshold=t)
                        for h in (5, 10) for t in (.03, .05)], ignore_index=True)
    single_consistency = summarize(single)
    pair = describe_pairs(panel)
    pair_consistency = consistency(pair)
    output.mkdir(parents=True, exist_ok=True)
    # No ticker-level data published. Factor aggregate statistics only.
    single_consistency.to_csv(output / "winner_single_factor_aggregate.csv", index=False)
    pair_consistency.to_csv(output / "winner_pair_aggregate.csv", index=False)
    manifest = {
        "status": "PROVISIONAL_RETROSPECTIVE_FACTOR_ASSOCIATION",
        "data_source": "FinanceData/marcap pinned historical 2017-22",
        "sample_modulus": modulus,
        "tickers": int(prices.ticker.nunique()),
        "factor_panel_rows": int(len(panel)),
        "single_consistent_signs": int(single_consistency.direction_consistent.sum()),
        "pair_positive_lift_both_periods": int(pair_consistency.direction_consistent.sum()),
        "not_officially_adjusted": True,
        "multiple_testing_corrected": False,
        "independent_validation": False,
        "net_portfolio_profit_verified": False,
        "holdout_2026_touched": False,
        "live_orders_allowed": False,
    }
    (output / "aggregate_manifest.json").write_text(json.dumps(manifest, indent=2))
    print(json.dumps(manifest))
    return manifest

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--data", type=Path, required=True)
    p.add_argument("--aggregate-output", type=Path, required=True)
    p.add_argument("--modulus", type=int, default=16)
    a = p.parse_args()
    run(a.data, a.aggregate_output, a.modulus)

if __name__ == "__main__":
    main()
