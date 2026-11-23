"""Retrospective descriptive profiles of stocks rising 5/10 sessions later.

Private v0.4 factor-matrix parquet parts are the ONLY inputs. No fresh price
download, no new indicator engineering, no ticker-level output or 2026 read.
Selection uses T+1 open to T+H close returns; no same-day hindsight signals.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import numpy as np
import pandas as pd

HORIZONS = (5, 10)
THRESHOLDS = (0.03, 0.05)
TRAIN_YEARS = (2019, 2020)
CHECK_YEARS = (2021, 2022)
MIN_ROWS = 30


def profile(panel: pd.DataFrame, *, horizon: int = 5,
            rise_threshold: float = .05) -> pd.DataFrame:
    """Factor rank-quintile enrichment, matched within each signal date.

    Winner frequency is P(future return >= threshold); this is NOT the
    profitability of buying the top quintile, and not a portfolio backtest.
    """
    if horizon not in HORIZONS or rise_threshold not in THRESHOLDS:
        raise ValueError("Predeclared horizons/thresholds only")
    label = f"forward_return_{horizon}"
    if not {"date", "ticker", label}.issubset(panel.columns):
        raise ValueError("Missing signal date, symbol or forward label")
    p = panel.copy()
    p["date"] = pd.to_datetime(p.date, errors="raise")
    if not p.date.dt.year.isin(TRAIN_YEARS + CHECK_YEARS).all():
        raise ValueError("Only 2019-22 explored research windows permitted")
    if p.duplicated(["date", "ticker"]).any():
        raise ValueError("Duplicate security/date")
    if "unsafe_session" in p and p["unsafe_session"].fillna(True).astype(bool).any():
        raise ValueError("Unsafe session cannot enter study")
    factors = sorted(c for c in p if c.startswith(("legacy__", "ta__")))
    if not factors:
        raise ValueError("No precomputed causal technical factors")
    records = []
    for factor in factors:
        for split, years in (("train_2019_20", TRAIN_YEARS),
                             ("check_2021_22", CHECK_YEARS)):
            z = p.loc[p.date.dt.year.isin(years),
                      ["date", label, factor]].copy()
            z = z.replace([np.inf, -np.inf], np.nan).dropna()
            if z.empty:
                continue
            z["winner"] = z[label] >= rise_threshold
            # Within-date percentile eliminates raw level/price scale.
            z["rank"] = z.groupby("date")[factor].rank(pct=True, method="average")
            counts = z.groupby("date")[factor].transform("count")
            z = z.loc[counts >= 20]
            if len(z) < MIN_ROWS:
                continue
            low, high = z.loc[z["rank"] <= .2], z.loc[z["rank"] > .8]
            if min(len(low), len(high)) < MIN_ROWS:
                continue
            base_rate = float(z["winner"].mean())
            high_rate, low_rate = float(high.winner.mean()), float(low.winner.mean())
            records.append({
                "factor": factor, "split": split, "horizon": horizon,
                "rise_threshold": rise_threshold,
                "observations": int(len(z)), "signal_days": int(z.date.nunique()),
                "winner_rate": base_rate,
                "top_quintile_winner_rate": high_rate,
                "bottom_quintile_winner_rate": low_rate,
                "top_minus_bottom_pp": 100 * (high_rate - low_rate),
                "top_lift": high_rate / base_rate if base_rate > 0 else np.nan,
                "bottom_lift": low_rate / base_rate if base_rate > 0 else np.nan,
                "top_n": int(len(high)), "bottom_n": int(len(low)),
            })
    return pd.DataFrame.from_records(records)


def summarize(profiles: pd.DataFrame) -> pd.DataFrame:
    """Compare *frozen factor direction* across two already explored periods.

    Reports BOTH directional signs, not a posthoc 'best strategy'.
    """
    if profiles.empty:
        return pd.DataFrame()
    train = profiles.loc[profiles.split.eq("train_2019_20")].copy()
    check = profiles.loc[profiles.split.eq("check_2021_22")].copy()
    keys = ["factor", "horizon", "rise_threshold"]
    a = train.merge(check, on=keys, suffixes=("_train", "_check"),
                    validate="one_to_one")
    a["direction_train"] = np.sign(a.top_minus_bottom_pp_train).astype(int)
    a["direction_check"] = np.sign(a.top_minus_bottom_pp_check).astype(int)
    a["direction_consistent"] = ((a.direction_train == a.direction_check)
                                 & a.direction_train.ne(0))
    a["minimum_absolute_gap_pp"] = a[[
        "top_minus_bottom_pp_train", "top_minus_bottom_pp_check"
    ]].abs().min(axis=1)
    a["observed_sign_consistency_only"] = True
    a["statistical_significance_established"] = False
    a["profitable_strategy_established"] = False
    return a.sort_values(["direction_consistent", "minimum_absolute_gap_pp"],
                         ascending=[False, False]).reset_index(drop=True)


def run(parts: list[Path], output: Path) -> dict:
    if not parts or not all(p.is_file() for p in parts):
        raise FileNotFoundError("Private factor matrix parquet parts required")
    frames = [pd.read_parquet(p) for p in parts]
    panel = pd.concat(frames, ignore_index=True)
    reports = [profile(panel, horizon=h, rise_threshold=t)
               for h in HORIZONS for t in THRESHOLDS]
    report = pd.concat(reports, ignore_index=True)
    summary = summarize(report)
    output.mkdir(parents=True, exist_ok=True)
    report.to_csv(output / "private_winner_factor_profiles.csv", index=False)
    summary.to_csv(output / "private_winner_factor_consistency.csv", index=False)
    manifest = {
        "status": "RETROSPECTIVE_DESCRIPTIVE_NOT_VALIDATED_ALPHA",
        "source": "private precomputed v0.4 factor matrix",
        "features": int(panel.filter(regex=r"^(legacy__|ta__)").shape[1]),
        "rows": int(len(panel)), "profiles": int(len(report)),
        "cross_period_consistent_signs": int(summary.direction_consistent.sum()),
        "periods_already_explored": ["2019-20", "2021-22"],
        "horizons": HORIZONS, "rise_thresholds": THRESHOLDS,
        "winner_definition": "T+1 open to T+H close gross return",
        "selection_bias": "posthoc winner label, NOT causal trading signal",
        "multiple_testing_adjusted": False,
        "official_issuer_actions_verified": False,
        "portfolio_net_profit_verified": False,
        "holdout_2026_opened": False,
        "live_orders_allowed": False,
    }
    (output / "aggregate_manifest.json").write_text(json.dumps(manifest, indent=2))
    print(json.dumps(manifest))
    return manifest


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--parts", nargs="+", type=Path, required=True)
    p.add_argument("--private-output", type=Path, required=True)
    a = p.parse_args()
    run(a.parts, a.private_output)


if __name__ == "__main__":
    main()
