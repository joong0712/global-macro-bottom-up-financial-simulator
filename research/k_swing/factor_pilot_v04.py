"""Private, stratified broad-factor PILOT, 2019-2023 only.

Never opens the locked 2026 confirmation set. Not an investable strategy:
no corporate-action verified adjusted returns, no fills, and no capital ledger.
The 2023 period was already inspected for older factors, so call it
exploratory validation (not an untouched holdout).
"""
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
import numpy as np
import pandas as pd

from .data import validate_prices, load_calendar
from .factor_matrix_v04 import one_symbol_matrix

TRAIN = {2019, 2020, 2021, 2022}
VALID = {2023}
HORIZONS = (5, 10)
TOP_K = (1, 3, 5, 10, 20)
PILOT_MODULUS = 8
MIN_CROSS_SECTION = 40


def is_sampled(code: str, modulus: int = PILOT_MODULUS) -> bool:
    if modulus <= 0:
        raise ValueError("invalid modulus")
    return int.from_bytes(hashlib.sha256(str(code).encode("ascii")).digest()[:4], "big") % modulus == 0


def _load_sample(private: Path, modulus: int) -> pd.DataFrame:
    pieces = []
    for year in range(2017, 2024):
        path = private / f"kswing_screened_{year}.csv.gz"
        if not path.is_file():
            raise FileNotFoundError(f"Missing screened private input: {path.name}")
        for chunk in pd.read_csv(path, dtype={"ticker": "string"},
                                 parse_dates=["date"], chunksize=100_000):
            selected = chunk.ticker.map(lambda x: is_sampled(x, modulus))
            part = chunk.loc[selected]
            if len(part):
                pieces.append(part)
    if not pieces:
        raise ValueError("No deterministic sample tickers")
    return validate_prices(pd.concat(pieces, ignore_index=True))


def _metrics_for_day(day: pd.DataFrame, features: list[str],
                     label: str, horizon: int) -> list[dict]:
    out = []
    target = day[label]
    for feature in features:
        subset = pd.DataFrame({"factor": day[feature], "target": target}).dropna()
        if len(subset) < MIN_CROSS_SECTION or subset.factor.nunique() < 2 or subset.target.nunique() < 2:
            continue
        rank_ic = subset.factor.rank().corr(subset.target.rank())
        if not np.isfinite(rank_ic):
            continue
        n = len(subset)
        sorted_y = subset.sort_values("factor", kind="stable").target.to_numpy()
        record = {
            "date": str(day.date.iloc[0].date()), "year": int(day.date.iloc[0].year),
            "factor": feature, "horizon": horizon, "cross_section": n,
            "rank_ic_raw": float(rank_ic),
            "universe_mean": float(subset.target.mean()),
        }
        for k in TOP_K:
            record[f"high_{k}"] = float(np.mean(sorted_y[-k:])) if n >= k else np.nan
            record[f"low_{k}"] = float(np.mean(sorted_y[:k])) if n >= k else np.nan
        out.append(record)
    return out


def aggregate(daily: pd.DataFrame, min_train_dates: int = 200) -> tuple[pd.DataFrame, pd.DataFrame]:
    train = daily.loc[daily.year.isin(TRAIN)]
    trained = train.groupby(["factor", "horizon"], as_index=False).agg(
        train_rank_ic=("rank_ic_raw", "mean"), train_days=("rank_ic_raw", "size")
    )
    trained["direction"] = np.where(trained.train_rank_ic >= 0, 1, -1)
    trained["eligible"] = trained.train_days >= min_train_dates
    trained["abs_ic"] = trained.train_rank_ic.abs()
    trained = trained.sort_values(["horizon", "eligible", "abs_ic", "factor"],
                                  ascending=[True, False, False, True])
    trained["train_rank"] = trained.groupby("horizon").cumcount() + 1
    trained["top5_train"] = trained.eligible & (trained.train_rank <= 5)
    z = daily.merge(trained[["factor", "horizon", "direction", "top5_train"]],
                    on=["factor", "horizon"], validate="many_to_one")
    z["oriented_ic"] = z.rank_ic_raw * z.direction
    for k in TOP_K:
        z[f"oriented_{k}"] = np.where(z.direction.eq(1), z[f"high_{k}"], z[f"low_{k}"])
        z[f"excess_{k}"] = z[f"oriented_{k}"] - z.universe_mean
    group = ["factor", "horizon"]
    summaries = []
    for split, years in (("train", TRAIN), ("validation_2023_reused", VALID)):
        part = z.loc[z.year.isin(years)]
        for (factor, horizon), g in part.groupby(group):
            rec = {
                "split": split, "factor": factor, "horizon": int(horizon),
                "direction_from_train": int(g.direction.iloc[0]),
                "top5_from_train": bool(g.top5_train.iloc[0]),
                "signal_days": int(len(g)),
                "mean_oriented_rank_ic": float(g.oriented_ic.mean()),
                "mean_cross_section": float(g.cross_section.mean()),
            }
            for k in TOP_K:
                rec[f"avg_top{k}_excess_gross"] = float(g[f"excess_{k}"].mean())
            summaries.append(rec)
    return pd.DataFrame(summaries), trained


def run(data_dir: Path, out_dir: Path, modulus: int = PILOT_MODULUS) -> dict:
    if modulus < 1:
        raise ValueError("modulus must be positive")
    if not (data_dir / "market_structure_quality.json").is_file():
        raise ValueError("v0.2 market quality audit required")
    audit = json.loads((data_dir / "market_structure_quality.json").read_text())
    if audit.get("certified_for_backtesting") is True:
        raise ValueError("No certified backtests in this pipeline")
    cal = audit.get("calendar", {})
    if cal.get("reference_only_dates") or cal.get("observed_only_dates"):
        raise ValueError("2017-2023 sample has unexpected calendar differences; stop")
    private = data_dir / "_private"
    sessions = load_calendar(private / "krx_observed_sessions.csv", _load_sample(private, modulus))
    if sessions.max().year != 2023:
        raise ValueError("Only 2017-2023 source sessions allowed for this pilot; 2026 remains locked")
    prices = _load_sample(private, modulus)
    feature_names = None
    matrices = []
    for ticker, group in prices.groupby("ticker", sort=True):
        x = one_symbol_matrix(group, sessions, "2019-01-01", "2023-12-31")
        if x.empty:
            continue
        context = group[["date", "ticker", "close", "turnover", "volume", "unsafe_session"]]
        x = x.merge(context, on=["date", "ticker"], how="left", validate="one_to_one")
        active = x.close.ge(1000) & x.turnover.ge(100_000_000) & x.volume.gt(0) & ~x.unsafe_session.fillna(True)
        x = x.loc[active]
        if not len(x):
            continue
        if feature_names is None:
            feature_names = [col for col in x if col.startswith("ta__") or col.startswith("legacy__")]
        x[feature_names] = x[feature_names].astype("float32")
        matrices.append(x[["date", "ticker", *feature_names, "forward_return_5", "forward_return_10"]])
    if not matrices:
        raise ValueError("No sampled signals")
    frame = pd.concat(matrices, ignore_index=True)
    days = pd.DatetimeIndex(sessions[sessions.year <= 2022][-10:]).union(
        pd.DatetimeIndex(sessions[sessions.year == 2023][-10:])
    )
    frame = frame.loc[~frame.date.isin(days)]
    daily = []
    for date, day in frame.groupby("date", sort=True):
        for horizon in HORIZONS:
            daily.extend(_metrics_for_day(day, feature_names,
                                          f"forward_return_{horizon}", horizon))
    summaries, training = aggregate(pd.DataFrame(daily))
    out_dir.mkdir(parents=True, exist_ok=True)
    # Only per-factor, per-period aggregates; no ticker-level or day-level raw outputs.
    summaries.to_csv(out_dir / "factor_pilot_aggregates.csv", index=False)
    training.to_csv(out_dir / "factor_pilot_training_ranks.csv", index=False)
    report = {
        "status": "EXPLORATORY_HASH_SAMPLED_FACTOR_PILOT_NOT_FULL_UNIVERSE",
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "upstream_source": "FinanceData/marcap (pinned 94c138df4bf7376be8d28f979edb14020e2a547a)",
        "sample_rule": f"sha256(ticker) first 4 bytes modulo {modulus} == 0, independent of survival",
        "sampled_tickers_with_signal_rows": int(frame.ticker.nunique()),
        "signal_rows": int(len(frame)),
        "unique_signal_days": int(frame.date.nunique()),
        "features": len(feature_names),
        "split": "training=2019-2022; exploratory reused validation=2023; 2024-25 not rerun; 2026 locked",
        "n_daily_factor_observations": int(len(daily)),
        "min_daily_stocks_per_factor": MIN_CROSS_SECTION,
        "topk_values": TOP_K,
        "warnings": [
            "Only a deterministic ticker hash subset, NOT representative of full market in size or sector",
            "2019-2023 adjusted corporate-action prices and historical security identity remain uncertified",
            "Top-K return means overlap and are not executed portfolio profit or investable alpha",
            "2023 validation for 18 legacy factors was already inspected in v0.3 and is not untouched",
            "Selection/multiple comparison bias remains even when training ranks are frozen",
            "No execution/liquidity overnight gap fill model, taxes or true investment costs",
        ],
        "holdout_2026_touched": False,
        "results_are_aggregate_only": True,
    }
    (out_dir / "factor_pilot_summary.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps({
        "status": report["status"], "features": report["features"],
        "sampled_tickers": report["sampled_tickers_with_signal_rows"],
        "signal_rows": report["signal_rows"],
        "daily_factor_observations": report["n_daily_factor_observations"],
        "validation_train_chosen": summaries.loc[summaries.split.eq("validation_2023_reused") & summaries.top5_from_train,
                            ["factor", "horizon", "signal_days", "mean_oriented_rank_ic", "avg_top10_excess_gross"]
                            ].round(5).to_dict("records"),
    }), flush=True)
    return report


def main():
    p = argparse.ArgumentParser(description="2019-2023 all-factor sampled pilot; 2026 LOCKED")
    p.add_argument("--data", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--modulus", type=int, default=PILOT_MODULUS)
    args = p.parse_args()
    run(args.data, args.output, args.modulus)


if __name__ == "__main__":
    main()
