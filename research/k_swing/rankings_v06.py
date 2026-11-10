"""K-SWING v0.6: retrospective leaderboard of published v0.4 factor aggregates.

No security-level market data; no independent holdout selection; no executed trades.
2023 leaderboard ranks are explicitly post-hoc and cannot choose a winning strategy.
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

HORIZONS = (5, 10)
TOP_K = (1, 3, 5, 10, 20)
COST_BPS = (20, 50, 100)
SOURCE_RUN = "https://github.com/joong0712/global-macro-bottom-up-financial-simulator/actions/runs/42871531605"


def build(aggregates: pd.DataFrame, training: pd.DataFrame) -> pd.DataFrame:
    a = aggregates.copy()
    t = training.copy()
    needed_a = {"factor", "horizon", "split", "signal_days", "mean_oriented_rank_ic",
                "direction_from_train"} | {f"avg_top{k}_excess_gross" for k in TOP_K}
    needed_t = {"factor", "horizon", "train_rank_ic", "train_days", "direction",
                "train_rank", "eligible"}
    if not needed_a.issubset(a.columns) or not needed_t.issubset(t.columns):
        raise ValueError("Missing v0.4 aggregated-factor columns")
    if set(a.split) != {"train", "validation_2023_reused"}:
        raise ValueError("Only train and already-inspected 2023 exploratory validation permitted")
    if set(a.horizon) != set(HORIZONS) or set(t.horizon) != set(HORIZONS):
        raise ValueError("Unexpected horizons")
    if a.duplicated(["split", "horizon", "factor"]).any() or t.duplicated(["horizon", "factor"]).any():
        raise ValueError("Duplicate factor/horizon/split keys")
    if a[["signal_days", "mean_oriented_rank_ic"]].isna().any().any():
        raise ValueError("Incomplete aggregated metrics")
    wide = a.pivot(index=["factor", "horizon"], columns="split", values=[
        "signal_days", "mean_oriented_rank_ic",
        *[f"avg_top{k}_excess_gross" for k in TOP_K]
    ])
    wide.columns = [f"{metric}__{period}" for metric, period in wide.columns]
    joined = t.merge(wide.reset_index(), on=["factor", "horizon"], validate="one_to_one")
    if joined[[f"avg_top10_excess_gross__{x}" for x in ("train", "validation_2023_reused")]].isna().any().any():
        raise ValueError("Missing required train/validation results")
    if not (joined["train_days"] >= 200).all() or not joined["eligible"].astype(bool).all():
        raise ValueError("Training factor eligibility not established")
    if not np.array_equal(np.sign(joined["train_rank_ic"].to_numpy()),
                          joined["direction"].to_numpy()):
        raise ValueError("Trained factor orientation differs from training IC")
    records: list[dict] = []
    for k in TOP_K:
        for row in joined.itertuples(index=False):
            item = row._asdict()
            factor = item["factor"]
            horizon = int(item["horizon"])
            # Pandas namedtuple sanitizes column names with repeated underscores;
            # positional indexing via original columns is safer.
            view = joined.loc[(joined.factor == factor) & joined.horizon.eq(horizon)].iloc[0]
            train = float(view[f"avg_top{k}_excess_gross__train"])
            val = float(view[f"avg_top{k}_excess_gross__validation_2023_reused"])
            train_ic = float(view["mean_oriented_rank_ic__train"])
            val_ic = float(view["mean_oriented_rank_ic__validation_2023_reused"])
            entry = {
                "factor": factor, "horizon": horizon, "top_k": int(k),
                "direction_from_2019_22_train": int(view["direction"]),
                "train_ic_rank": int(view["train_rank"]),
                "train_mean_oriented_ic": train_ic,
                "explored_2023_mean_oriented_ic": val_ic,
                "train_signal_days": int(view["signal_days__train"]),
                "explored_2023_signal_days": int(view["signal_days__validation_2023_reused"]),
                "train_avg_excess_gross": train,
                "explored_2023_avg_excess_gross": val,
                "sign_ic_consistent_train_2023": train_ic > 0 and val_ic > 0,
                "positive_excess_both_periods": train > 0 and val > 0,
                "explored_2023_minus_train_excess": val-train,
            }
            for bps in COST_BPS:
                entry[f"explored_2023_excess_minus_assumed_{bps}bps"] = val - bps/10000
            records.append(entry)
    result = pd.DataFrame(records)
    result["exploratory_2023_excess_rank"] = result.groupby(
        ["horizon", "top_k"])["explored_2023_avg_excess_gross"].rank(
        method="min", ascending=False).astype(int)
    result["training_excess_rank"] = result.groupby(
        ["horizon", "top_k"])["train_avg_excess_gross"].rank(
        method="min", ascending=False).astype(int)
    result = result.sort_values(
        ["horizon","top_k","exploratory_2023_excess_rank","factor"]
    ).reset_index(drop=True)
    assert len(result) == len(t) * len(TOP_K)
    return result


def run(source: Path, output: Path) -> dict:
    if not source.is_dir():
        raise FileNotFoundError(source)
    a = pd.read_csv(source/"factor_pilot_aggregates.csv")
    t = pd.read_csv(source/"factor_pilot_training_ranks.csv")
    table = build(a, t)
    output.mkdir(parents=True, exist_ok=True)
    table.to_csv(output/"factor_leaderboard_188_v06.csv", index=False)
    leaders = table.loc[table.exploratory_2023_excess_rank.le(10)].copy()
    leaders.to_csv(output/"exploratory_top10_each_k_horizon.csv", index=False)
    # Training-selected Top 5 by IC, NOT backfitted to 2023 gross return.
    selected = table.loc[table.train_ic_rank.le(5)].copy()
    selected.to_csv(output/"train_ic_selected_oos_descriptive.csv", index=False)
    manifest = {
        "status": "RETROSPECTIVE_EXPLORATORY_NOT_A_STRATEGY",
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "source_actions_run": SOURCE_RUN,
        "factor_count": int(t.factor.nunique()), "factor_horizon_count": len(t),
        "leaderboard_rows": len(table),
        "horizons": HORIZONS, "k": TOP_K,
        "selection_direction": "2019-2022 training only",
        "ordering": "RETROSPECTIVE 2023 gross excess; explicitly not independent validation",
        "training_selected": "top five by absolute train IC (independent of 2023 profit)",
        "cost_columns": "Illustrative cost subtracted from excess vs zero-cost benchmark; NOT portfolio net return",
        "known_limits": [
            "2023 inspection invalidates picking the best strategy by this ranking",
            "Some returns unavailable for delisted/suspended securities; missing labels may bias estimates",
            "K=1,3,5,10,20 selected ex post in the reused validation period",
            "Highly correlated indicators and multiple comparisons; no p-value/false discovery guarantee",
            "No capital ledger, position overlap, actual execution, or verified corporate-action price adjustments",
            "Hash-sampled historical tickers rather than a fully verified historical stock universe",
        ],
        "holdout_2026_opened": False,
    }
    (output/"leaderboard_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({
        "status": manifest["status"], "factors": manifest["factor_count"],
        "rows":len(table),
        "posthoc_2023_winners":leaders.loc[leaders.exploratory_2023_excess_rank.eq(1),
               ["horizon","top_k","factor","explored_2023_avg_excess_gross"]].round(6).to_dict("records"),
    }, ensure_ascii=False), flush=True)
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description="v0.6 188-indicator retrospective ranking; no holdout")
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    run(args.source, args.output)


if __name__ == "__main__":
    main()
