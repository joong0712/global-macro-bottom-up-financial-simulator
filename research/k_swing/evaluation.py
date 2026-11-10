"""Descriptive factor analysis; Top-K cohorts are not investable portfolio PnL."""
import numpy as np
import pandas as pd
from .factors import FACTOR_NAMES


def daily_ic(values: pd.DataFrame, factor: str, target: str,
             min_cross_section: int = 5) -> pd.Series:
    result = {}
    for date, group in values[["date", factor, target]].dropna().groupby("date", sort=True):
        if len(group) < min_cross_section or group[factor].nunique() < 2 or group[target].nunique() < 2:
            continue
        ic = group[factor].rank().corr(group[target].rank())
        if np.isfinite(ic):
            result[date] = float(ic)
    return pd.Series(result, dtype="float64")


def summarize_factor(values: pd.DataFrame, factor: str, horizon: int,
                     direction: int, top_k: int = 5, roundtrip_bps: float = 20.,
                     min_cross_section: int = 5) -> dict:
    target = f"forward_return_{horizon}"
    subset = values[["date", factor, target]].dropna()
    ic = daily_ic(subset, factor, target, min_cross_section)
    cohorts = []
    for date, day in subset.groupby("date", sort=True):
        if len(day) < max(top_k, min_cross_section):
            continue
        picks = day.loc[(day[factor] * direction).nlargest(top_k).index, target]
        cohorts.append((float(picks.mean()), float((picks > 0).mean())))
    return {
        "factor": factor, "horizon": horizon, "direction": int(direction),
        "n_samples": len(subset), "n_ic_dates": len(ic),
        "mean_rank_ic": float(ic.mean()) if len(ic) else None,
        "median_rank_ic": float(ic.median()) if len(ic) else None,
        "ic_positive_fraction": float((ic > 0).mean()) if len(ic) else None,
        "n_topk_dates": len(cohorts),
        "avg_topk_gross_return": float(np.mean([x[0] for x in cohorts])) if cohorts else None,
        "avg_topk_net_return_approx": (
            float(np.mean([x[0] for x in cohorts]) - roundtrip_bps / 10000)
            if cohorts else None
        ),
        "avg_topk_win_fraction": float(np.mean([x[1] for x in cohorts])) if cohorts else None,
    }


def run_evaluation(panel: pd.DataFrame, factors: tuple[str, ...] = FACTOR_NAMES,
                   horizons: tuple[int, ...] = (5, 10), top_k: int = 5,
                   roundtrip_bps: float = 20., min_cross_section: int = 5,
                   min_train_ic_days: int = 20) -> tuple[pd.DataFrame, pd.DataFrame]:
    rows, decisions = [], []
    training = panel.loc[panel["split"].eq("train")]
    for horizon in horizons:
        target = f"forward_return_{horizon}"
        for factor in factors:
            train_ic = daily_ic(training, factor, target, min_cross_section)
            sufficient = len(train_ic) >= min_train_ic_days
            direction = 1 if not sufficient or float(train_ic.mean()) >= 0 else -1
            decisions.append({
                "factor": factor, "horizon": horizon,
                "train_ic_days": len(train_ic), "direction_from_train": direction,
                "sufficient_train_coverage": sufficient,
            })
            for split in ("train", "validation", "test"):
                metrics = summarize_factor(
                    panel.loc[panel["split"].eq(split)], factor, horizon, direction,
                    top_k, roundtrip_bps, min_cross_section,
                )
                metrics["split"] = split
                metrics["sufficient_train_coverage"] = sufficient
                rows.append(metrics)
    metrics = pd.DataFrame(rows)
    ranking = pd.DataFrame(decisions)
    training_ic = metrics.loc[metrics["split"].eq("train"), ["factor", "horizon", "mean_rank_ic"]].copy()
    training_ic["abs_training_ic"] = training_ic["mean_rank_ic"].abs()
    ranking = ranking.merge(
        training_ic[["factor", "horizon", "abs_training_ic"]], on=["factor", "horizon"]
    )
    ranking = ranking.sort_values(
        ["sufficient_train_coverage", "abs_training_ic"],
        ascending=[False, False], na_position="last",
    ).reset_index(drop=True)
    return metrics, ranking
