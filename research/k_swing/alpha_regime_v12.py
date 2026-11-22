"""K-SWING v1.2: frozen market regime -> one predeclared swing arm per day.

All regime features are derived from AS-OF T sampled market cross-section.
No post-hoc best-arm selection based on 2021-22 returns.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

from .alpha_candidates_v11 import build_candidates
from .alpha_common_v12 import (
    EVAL_FIRST, EVAL_LAST, feature_panel, load_screened_sample,
    assert_protected_eval_frame,
)
from .vcr_execution_v10 import simulate_brackets


def regime_by_date(panel: pd.DataFrame) -> pd.DataFrame:
    """Use only time-T cross-sectional characteristics; no forward bars."""
    if panel.empty or "r1" not in panel or "to_ma60" not in panel:
        raise ValueError("As-of price feature panel required")
    daily = panel.assign(above60=panel.to_ma60.gt(0).astype(float)).groupby("date").agg(
        median_return=("r1", "median"),
        breadth=("above60", "mean"),
        n_eligible=("ticker", "nunique"),
    ).sort_index()
    # Median stock return is a *sample breadth proxy*, not an actual KOSPI index.
    r = daily.median_return.clip(lower=-.5, upper=.5)
    daily["sample_market20"] = (1 + r).rolling(20, min_periods=20).apply(
        np.prod, raw=True).sub(1)
    daily["sample_market60"] = (1 + r).rolling(60, min_periods=60).apply(
        np.prod, raw=True).sub(1)
    bullish = daily.sample_market60.ge(.03) & daily.breadth.ge(.55)
    bearish = daily.sample_market20.le(-.04) & daily.breadth.le(.45)
    ready = daily.n_eligible.ge(10) & daily.sample_market60.notna()
    daily["regime"] = "insufficient_history"
    daily.loc[ready, "regime"] = "sideways"
    daily.loc[ready & bullish, "regime"] = "bull"
    daily.loc[ready & bearish & ~bullish, "regime"] = "bear"
    return daily.reset_index()[["date", "regime", "n_eligible"]]


ROUTE = {
    "bull": "momentum52",
    "bear": "reversal3",
    "sideways": "vcr_trend",
    # insufficient_history intentionally holds cash
}


def route_signals(predeclared_candidates: pd.DataFrame,
                  regimes: pd.DataFrame) -> pd.DataFrame:
    required = {"date", "ticker", "score", "turnover", "strategy"}
    if not required.issubset(predeclared_candidates):
        raise ValueError("Predeclared v1.1 candidates required")
    if not {"date", "regime"}.issubset(regimes):
        raise ValueError("Predeclared market regime required")
    if regimes.date.duplicated().any():
        raise ValueError("Duplicate time-T regime")
    routing = regimes[["date", "regime"]].copy()
    routing["strategy"] = routing.regime.map(ROUTE)
    merged = predeclared_candidates.merge(routing[["date", "strategy"]],
                                           on=["date", "strategy"],
                                           how="inner", validate="many_to_one")
    return merged[["date", "ticker", "score", "turnover"]].sort_values(
        ["date", "score", "ticker"], kind="stable").reset_index(drop=True)


def run(data_dir: Path, output_dir: Path, *, modulus: int = 16):
    bars, dates = load_screened_sample(data_dir, modulus)
    panel = feature_panel(bars, dates)
    # Entire 2017-2022 panel is used only to derive trailing as-of regime state.
    regimes = regime_by_date(panel)
    eligible = regimes.loc[regimes.date.between(EVAL_FIRST, EVAL_LAST)].copy()
    assert_protected_eval_frame(eligible)
    predeclared = build_candidates(bars, dates, first_signal="2021-01-01")
    predeclared = predeclared.loc[
        predeclared.date.between(EVAL_FIRST, EVAL_LAST)]
    selected = route_signals(predeclared, eligible)
    scenarios = []
    for horizon in (5, 10):
        result = simulate_brackets(
            bars, selected, dates, horizon=horizon, top_k=10,
            stop_pct=.03, take_pct=.08,
            initial_cash_krw=100_000_000, ticket_krw=5_000_000,
            max_positions=10, assumed_roundtrip_bps=50.)
        scenarios.append({"horizon": horizon,
                          "selected_predeclared_signals": len(selected),
                          **result})
    output = {
        "track": "precommitted_market_regime_switcher",
        "status": "REUSED_DEVELOPMENT_DATA_NOT_VERIFIED_INVESTABLE_ALPHA",
        "evaluation": "2021-01-01 to 2022-12-15, previously inspected",
        "market_proxy": "median daily return and breadth of historically eligible sampled stocks (not official KOSPI)",
        "frozen_route": ROUTE,
        "frozen_regime_thresholds": {
            "bull": "60-day sampled median-market return >= 3% and breadth >= 55%",
            "bear": "20-day sampled median-market return <= -4% and breadth <= 45%",
            "other": "sideways VCR trend or insufficient history no trade",
        },
        "regime_counts": {str(k): int(v) for k, v in
                          eligible.regime.value_counts().to_dict().items()},
        "sampled_tickers": int(bars.ticker.nunique()),
        "sample_hash_modulus": modulus,
        "2023_2026_holdouts_opened": False,
        "official_corporate_actions_delistings_fills_taxes_verified": False,
        "results": scenarios,
        "warning": ("Market proxy and strategy trade opportunities are not equal exposure. "
                    "No issuer, effective tax, exchange auction, or real trading alpha verification."),
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "v12_regime_aggregate_only.json").write_text(
        json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"track": output["track"], "status": output["status"],
                      "regime_counts": output["regime_counts"],
                      "results": [{
                          "horizon": x["horizon"],
                          "signals": x["selected_predeclared_signals"],
                          "closed": x["completed_trades"], "status": x["status"],
                          "return": x["hypothetical_net_return_if_resolved"],
                          "mdd": x["hypothetical_marked_mdd_if_resolved"]
                      } for x in scenarios], "holdouts_locked": True}), flush=True)
    return output


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--modulus", type=int, default=16)
    args = parser.parse_args()
    run(args.data, args.output, modulus=args.modulus)


if __name__ == "__main__":
    main()
