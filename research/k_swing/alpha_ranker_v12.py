"""Frozen LightGBM 5/10-day Korean-stock ranker, research-only.

Model fitted strictly on 2019-2020 *matured* bracket PnL labels and
T-close predictors. No evaluation labels or 2023-2026 OHLCV are read.
Evaluation is reused 2021-2022 DEVELOPMENT data, not independent OOS.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

from .alpha_common_v12 import (
    FEATURE_COLS, TRAIN_FIRST, TRAIN_LAST, EVAL_FIRST, EVAL_LAST,
    load_screened_sample, feature_panel, training_bracket_labels,
    assert_protected_eval_frame,
)
from .vcr_execution_v10 import simulate_brackets

MODEL_HYPERPARAMETERS = {
    "n_estimators": 120, "learning_rate": .04,
    "num_leaves": 15, "min_child_samples": 100,
    "reg_lambda": 10.0, "max_depth": -1,
    "n_jobs": 2, "random_state": 42,
    "verbosity": -1, "deterministic": True,
    "force_col_wise": True,
}
PREDICTION_FLOOR = 0.0


def rank_from_predictions(frame: pd.DataFrame, predictions) -> pd.DataFrame:
    if len(predictions) != len(frame):
        raise ValueError("Prediction/sample length mismatch")
    if not np.isfinite(np.asarray(predictions, dtype=float)).all():
        raise ValueError("Non-finite predictions invalid")
    eligible = np.asarray(predictions, dtype=float) > PREDICTION_FLOOR
    selected = frame.loc[eligible, ["date", "ticker", "turnover"]].copy()
    selected["score"] = -np.asarray(predictions, dtype=float)[eligible]
    return selected


def run(data_dir: Path, output_dir: Path, *, modulus: int = 16):
    from lightgbm import LGBMRegressor

    bars, dates = load_screened_sample(data_dir, modulus)
    panel = feature_panel(bars, dates)
    tr = panel.loc[panel.date.between(TRAIN_FIRST, TRAIN_LAST)].copy()
    evaluation = panel.loc[panel.date.between(EVAL_FIRST, EVAL_LAST)].copy()
    assert_protected_eval_frame(evaluation)
    if len(tr) < 400 or len(evaluation) < 100:
        raise ValueError("Not enough screened stocks in chronological train/development windows")
    scenarios = []
    for horizon in (5, 10):
        labels = training_bracket_labels(bars, tr[["date", "ticker"]], dates, horizon)
        train = tr.merge(labels, on=["date", "ticker"], how="inner",
                         validate="one_to_one")
        if len(train) < 300:
            raise ValueError("Training labels insufficient after safe-bar and maturity exclusions")
        if train.date.max() > TRAIN_LAST or train.date.max() >= evaluation.date.min():
            raise ValueError("Chronological signal boundary violated")
        model = LGBMRegressor(**MODEL_HYPERPARAMETERS)
        model.fit(train[list(FEATURE_COLS)],
                  train.net_bracket_label.to_numpy(dtype=float))
        pred = model.predict(evaluation[list(FEATURE_COLS)])
        selected = rank_from_predictions(evaluation, pred)
        result = simulate_brackets(
            bars, selected, dates,
            horizon=horizon, top_k=10,
            stop_pct=.03, take_pct=.08,
            initial_cash_krw=100_000_000, ticket_krw=5_000_000,
            max_positions=10, assumed_roundtrip_bps=50.)
        scenarios.append({
            "horizon": horizon, "n_training_examples": len(train),
            "n_evaluation_candidates": len(evaluation),
            "n_positive_predicted_signals": len(selected),
            "prediction_threshold_net": PREDICTION_FLOOR,
            **result,
        })
    output = {
        "track": "lightgbm_bracket_return_ranker",
        "status": "REUSED_DEVELOPMENT_DATA_NOT_VERIFIED_INVESTABLE_ALPHA",
        "training": "2019-01-01 through 2020-12-01 (label mature by 2020-12-15)",
        "development": "2021-01-01 through 2022-12-15 (previously inspected)",
        "model": MODEL_HYPERPARAMETERS,
        "features": list(FEATURE_COLS),
        "sampled_tickers": int(bars.ticker.nunique()),
        "sample_hash_modulus": modulus,
        "exit_target_aligned_to_bracket": True,
        "positive_net_predicted_return_floor": PREDICTION_FLOOR,
        "2023_2026_holdouts_opened": False,
        "official_corporate_actions_delistings_fills_taxes_verified": False,
        "results": scenarios,
        "warning": "No issuer identity, delisting, KRX auction, market impact, after-tax return certification. No live orders.",
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "v12_lightgbm_aggregate_only.json").write_text(
        json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({
        "track": output["track"], "status": output["status"],
        "results": [{
            "horizon": r["horizon"], "training": r["n_training_examples"],
            "candidates": r["n_positive_predicted_signals"],
            "closed": r["completed_trades"], "status": r["status"],
            "return": r["hypothetical_net_return_if_resolved"],
            "mdd": r["hypothetical_marked_mdd_if_resolved"],
        } for r in scenarios], "holdouts_locked": True,
    }), flush=True)
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
