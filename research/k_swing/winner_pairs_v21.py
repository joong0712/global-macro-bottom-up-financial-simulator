"""Pre-registered 2-factor interactions for future rising-stock cohorts.

Descriptive association only. Uses same-day percentile ranks of causal
precomputed factors. Does not treat historical selection as independent
validation, and does not publish symbol/date-level records.
"""
from __future__ import annotations
import argparse
import json
from itertools import combinations
from pathlib import Path
import numpy as np
import pandas as pd

PAIRS = (
    ("ta__rsi_14", "ta__volume_ratio_20"),
    ("ta__macd_hist", "ta__atr_pct_14"),
    ("ta__ichi_cloud_top_gap", "ta__volume_ratio_20"),
)
HORIZONS = (5, 10)
RISE = (.03, .05)
PERIODS = (("2019_20", (2019, 2020)), ("2021_22", (2021, 2022)))
MIN_GROUP = 30


def describe_pairs(panel: pd.DataFrame, pairs=PAIRS) -> pd.DataFrame:
    if not {"date", "ticker", "forward_return_5", "forward_return_10"}.issubset(panel):
        raise ValueError("Required precomputed label columns absent")
    z = panel.copy()
    z["date"] = pd.to_datetime(z["date"])
    if not z.date.dt.year.isin((2019, 2020, 2021, 2022)).all():
        raise ValueError("Only previously explored 2019-22 data allowed")
    if z.duplicated(["date", "ticker"]).any():
        raise ValueError("Duplicate security-date rows")
    if "unsafe_session" in z and z.unsafe_session.fillna(True).astype(bool).any():
        raise ValueError("Unsafe rows rejected")
    required = set(sum((list(pair) for pair in pairs), []))
    if not required.issubset(z.columns):
        raise ValueError("Missing preregistered factor columns")
    for factor in required:
        z[factor] = pd.to_numeric(z[factor], errors="coerce")
        z[factor] = z[factor].replace([np.inf, -np.inf], np.nan)
        z[f"_pct_{factor}"] = z.groupby("date")[factor].rank(pct=True)
    records = []
    for (first, second) in pairs:
        for name, years in PERIODS:
            p = z.loc[z.date.dt.year.isin(years)].copy()
            p = p.dropna(subset=[first, second])
            day_n = p.groupby("date")["ticker"].transform("count")
            p = p.loc[day_n >= 40]
            if p.empty:
                continue
            x = p[f"_pct_{first}"]
            y = p[f"_pct_{second}"]
            # Fixed quadrants; no search over thresholds or direction.
            groups = {
                "high_high": (x > .8) & (y > .8),
                "high_low": (x > .8) & (y <= .2),
                "low_high": (x <= .2) & (y > .8),
                "low_low": (x <= .2) & (y <= .2),
            }
            for h in HORIZONS:
                label = f"forward_return_{h}"
                valid = p[label].notna()
                reference = p.loc[valid, label]
                for threshold in RISE:
                    base = float((reference >= threshold).mean()) if len(reference) >= MIN_GROUP else np.nan
                    for quadrant, mask in groups.items():
                        selected = p.loc[valid & mask, label]
                        rate = float((selected >= threshold).mean()) if len(selected) >= MIN_GROUP else np.nan
                        records.append({
                            "factor_a": first, "factor_b": second,
                            "period": name, "horizon": h, "rise_threshold": threshold,
                            "quadrant": quadrant, "observations": len(selected),
                            "reference_observations": len(reference),
                            "reference_winner_rate": base,
                            "quadrant_winner_rate": rate,
                            "lift": rate / base if np.isfinite(rate) and np.isfinite(base) and base > 0 else np.nan,
                            "excess_probability_pp": 100 * (rate-base) if np.isfinite(rate) and np.isfinite(base) else np.nan,
                        })
    return pd.DataFrame(records)


def consistency(result: pd.DataFrame) -> pd.DataFrame:
    if result.empty:
        return pd.DataFrame()
    keys = ["factor_a", "factor_b", "horizon", "rise_threshold", "quadrant"]
    train = result.loc[result.period.eq("2019_20")].drop(columns="period")
    check = result.loc[result.period.eq("2021_22")].drop(columns="period")
    x = train.merge(check, on=keys, suffixes=("_early", "_late"), validate="one_to_one")
    x["direction_consistent"] = (
        x.excess_probability_pp_early.notna() &
        x.excess_probability_pp_late.notna() &
        x.excess_probability_pp_early.gt(0) &
        x.excess_probability_pp_late.gt(0))
    x["independent_validation"] = False
    x["after_cost_profit_established"] = False
    return x.sort_values(["direction_consistent", "factor_a", "factor_b"],
                         ascending=[False, True, True]).reset_index(drop=True)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--parts", nargs="+", type=Path, required=True)
    p.add_argument("--private-output", type=Path, required=True)
    a = p.parse_args()
    if not a.parts or not all(x.is_file() for x in a.parts):
        raise FileNotFoundError("Private factor parquet parts unavailable")
    panel = pd.concat([pd.read_parquet(x) for x in a.parts], ignore_index=True)
    results = describe_pairs(panel)
    summary = consistency(results)
    a.private_output.mkdir(parents=True, exist_ok=True)
    results.to_csv(a.private_output / "private_pair_quadrants.csv", index=False)
    summary.to_csv(a.private_output / "private_pair_consistency.csv", index=False)
    public = {"status": "DESCRIPTIVE_ONLY",
              "candidate_pairs": len(PAIRS),
              "rows": len(results),
              "two_period_positive_lifts": int(summary.direction_consistent.sum()) if not summary.empty else 0,
              "private_market_data_available": True,
              "2026_holdout_touched": False,
              "after_cost_profit_verified": False}
    (a.private_output / "aggregate_manifest.json").write_text(json.dumps(public, indent=2))
    print(json.dumps(public))


if __name__ == "__main__":
    main()
