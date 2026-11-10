"""K-SWING v0.3: real-data factor validation on quarantined historic prices.

Cross-sectional Rank IC and event-window forward returns are *descriptive*,
not a portfolio backtest, verified alpha, or a claim of investability.
No raw prices or security-level selections leave the private runner.
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from .factors import FACTOR_NAMES
from .targets import build_panel


TRAIN_YEARS = (2019, 2020, 2021, 2022)
VALIDATION_YEARS = (2023,)
TEST_YEARS = (2024, 2025)
HORIZONS = (5, 10)
KNOWN_XKRX_DISCREPANCIES = {"2026-06-03", "2026-07-17"}


def validate_market_quality(report: dict) -> dict:
    """Fail closed if the source/session audit reports unexplained mismatch."""
    if report.get("certified_for_backtesting") is True:
        raise ValueError("This program must not imply certified executable backtests")
    cal = report.get("calendar") or {}
    unexpected = set(cal.get("observed_only_dates", []))
    reference_only = set(cal.get("reference_only_dates", []))
    if unexpected or reference_only - KNOWN_XKRX_DISCREPANCIES:
        raise ValueError(
            "Unexplained exchange-calendar disagreement: "
            f"reference_only={sorted(reference_only)}, source_only={sorted(unexpected)}"
        )
    return {"reference_only": sorted(reference_only), "source_only": sorted(unexpected)}


def _load_year(private: Path, year: int) -> pd.DataFrame:
    path = private / f"kswing_screened_{year}.csv.gz"
    if not path.is_file():
        raise FileNotFoundError(f"Screened prices missing for year {year}: {path}")
    frame = pd.read_csv(path, dtype={"ticker": "string"}, parse_dates=["date"])
    required = {"date", "ticker", "open", "high", "low", "close", "volume", "turnover", "unsafe_session"}
    if not required.issubset(frame.columns):
        raise ValueError(f"Input is not v0.2 screened data: {path}")
    if frame["unsafe_session"].isna().any():
        raise ValueError(f"Missing quarantine flags: {path}")
    return frame


def _daily_cohorts(panel: pd.DataFrame, year: int, min_turnover: float,
                   min_price: float, min_names: int, top_k: int,
                   embargo_dates: set[pd.Timestamp]) -> list[dict]:
    """Use only eligibility observable at signal close; future return used only as label."""
    frame = panel.loc[
        (panel["date"].dt.year == year)
        & (panel["turnover"] >= min_turnover)
        & (panel["close"] >= min_price)
        & (panel["volume"] > 0)
        & (~panel["unsafe_session"].fillna(True).astype(bool))
        & (~panel["date"].isin(embargo_dates))
    ].copy()
    records: list[dict] = []
    for horizon in HORIZONS:
        label = f"forward_return_{horizon}"
        valid = frame.loc[frame[label].notna(), ["date", label, *FACTOR_NAMES]]
        for date, day in valid.groupby("date", sort=True):
            baseline = day[label].dropna()
            for factor in FACTOR_NAMES:
                usable = day[[factor, label]].dropna()
                if len(usable) < max(min_names, top_k) or usable[factor].nunique() < 2:
                    continue
                corr = usable[factor].rank().corr(usable[label].rank())
                if not np.isfinite(corr):
                    continue
                top = usable.nlargest(top_k, factor)[label]
                bottom = usable.nsmallest(top_k, factor)[label]
                records.append({
                    "date": date, "year": year, "factor": factor, "horizon": horizon,
                    "n_eligible_for_factor": len(usable),
                    "rank_ic_raw": float(corr),
                    "high_topk_gross": float(top.mean()),
                    "low_topk_gross": float(bottom.mean()),
                    "high_topk_win": float((top > 0).mean()),
                    "low_topk_win": float((bottom > 0).mean()),
                    "universe_mean_return": float(baseline.mean()),
                    "universe_n": len(baseline),
                })
    return records


def summarize(daily: pd.DataFrame, roundtrip_bps: float = 20.,
              min_training_dates: int = 100) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    """Freeze direction and factor selection on training data alone."""
    if daily.empty:
        raise ValueError("No factor observations to evaluate")
    labels = {
        "train": set(TRAIN_YEARS),
        "validation": set(VALIDATION_YEARS),
        "test": set(TEST_YEARS),
    }
    source_train = daily.loc[daily.year.isin(TRAIN_YEARS)].copy()
    training = source_train.groupby(["horizon", "factor"], as_index=False).agg(
        train_mean_ic=("rank_ic_raw", "mean"),
        train_ic_days=("rank_ic_raw", "size"),
    )
    training["direction"] = np.where(training["train_mean_ic"] >= 0, 1, -1)
    training["abs_train_ic"] = training["train_mean_ic"].abs()
    training["eligible_for_ranking"] = training["train_ic_days"] >= min_training_dates
    training = training.sort_values(
        ["horizon", "eligible_for_ranking", "abs_train_ic", "factor"],
        ascending=[True, False, False, True],
    )
    training["train_rank"] = training.groupby("horizon").cumcount() + 1
    training["preselected"] = training.eligible_for_ranking & (training.train_rank <= 5)

    joined = daily.merge(training, on=["horizon", "factor"], how="inner", validate="many_to_one")
    joined["selected_gross"] = np.where(joined.direction.eq(1), joined.high_topk_gross, joined.low_topk_gross)
    joined["selected_win"] = np.where(joined.direction.eq(1), joined.high_topk_win, joined.low_topk_win)
    joined["oriented_ic"] = joined.rank_ic_raw * joined.direction

    reports = []
    for split, year_set in labels.items():
        period = joined.loc[joined.year.isin(year_set)]
        grouped = period.groupby(["horizon", "factor"], sort=True)
        for (horizon, factor), group in grouped:
            avg = group.selected_gross.mean()
            benchmark = group.universe_mean_return.mean()
            reports.append({
                "split": split, "horizon": int(horizon), "factor": factor,
                "direction_from_training": int(group.direction.iloc[0]),
                "preselected_using_train_only": bool(group.preselected.iloc[0]),
                "signal_days": int(len(group)),
                "mean_daily_rank_ic": float(group.oriented_ic.mean()),
                "raw_rank_ic": float(group.rank_ic_raw.mean()),
                "ic_std": float(group.oriented_ic.std(ddof=1)),
                "share_positive_daily_ic": float((group.oriented_ic > 0).mean()),
                "topk_avg_gross_return": float(avg),
                "topk_avg_net_approx": float(avg - roundtrip_bps / 10000),
                "universe_avg_gross_return": float(benchmark),
                "topk_avg_excess_gross": float(avg - benchmark),
                "topk_win_rate_mean": float(group.selected_win.mean()),
                "mean_eligible_names": float(group.n_eligible_for_factor.mean()),
            })
    results = pd.DataFrame(reports).sort_values(["horizon", "factor", "split"])
    if results.empty:
        raise ValueError("No split summaries")
    selection = training.loc[
        training.preselected, ["horizon", "factor", "direction", "train_mean_ic",
                               "train_ic_days", "train_rank"]
    ].copy()
    summary = {
        "design": "EXPLORATORY, NOT INVESTABLE / NOT A PORTFOLIO BACKTEST",
        "train_years": TRAIN_YEARS, "validation_years": VALIDATION_YEARS,
        "test_years": TEST_YEARS,
        "entry": "T+1 open", "exit": "T+H close (H=5,10)",
        "factor_direction_and_top5_selection": "Fixed solely using train observations 2019-2022",
        "factor_mean_ic": "Equal-weight average across signal days, not pooled stock returns",
        "roundtrip_bps_approx": roundtrip_bps,
        "topk_mean_return_warning": "Overlapping holding windows, capital, taxes, fees, fillability, delisted share identity and corporate-action correction are NOT simulated.",
        "test_warning": "The test set must not be used for iterative tuning or formula selection. Multiple tested factors imply selection bias.",
        "prices_warning": "Unverified raw-price corporate-action adjustment and historical ordinary-share universe; quarantined candidates are heuristics.",
    }
    return results, selection, summary


def run(data_dir: Path, dest: Path,
        min_turnover: float = 100_000_000.,
        min_price: float = 1000.,
        min_names: int = 50, top_k: int = 10,
        roundtrip_bps: float = 20.) -> dict:
    if min_turnover < 0 or min_price <= 0 or min_names < 5 or top_k < 1 or roundtrip_bps < 0:
        raise ValueError("Invalid thresholds")
    if top_k > min_names:
        raise ValueError("top_k cannot exceed min_names")
    private = data_dir / "_private"
    q = json.loads((data_dir / "market_structure_quality.json").read_text(encoding="utf-8"))
    cal_report = validate_market_quality(q)
    sessions = pd.DatetimeIndex(
        pd.to_datetime(pd.read_csv(private / "krx_observed_sessions.csv")["date"])
    ).normalize().unique().sort_values()
    if len(sessions) < 1000:
        raise ValueError("Insufficient exchange sessions")
    if not set(TRAIN_YEARS + VALIDATION_YEARS + TEST_YEARS).issubset(set(sessions.year)):
        raise ValueError("Required research years absent from data")
    # Remove each period's last ten trading dates from its labels so its
    # outcome is not observed in the next research regime.
    embargo = set()
    for boundary_year in (2022, 2023, 2025):
        earlier = sessions[sessions.year <= boundary_year]
        embargo.update(pd.Timestamp(x) for x in earlier[-10:])
    daily = []
    cache: dict[int, pd.DataFrame] = {}
    total_signal_bars = 0
    for year in TRAIN_YEARS + VALIDATION_YEARS + TEST_YEARS:
        for yy in (year - 1, year, year + 1):
            if yy not in cache:
                cache[yy] = _load_year(private, yy)
        # 160 previous sessions covers every finite feature lookback and
        # converges the 26-day EMA to negligible truncation error.
        past_sessions = sessions[sessions < pd.Timestamp(year, 1, 1)]
        upcoming = sessions[sessions > pd.Timestamp(year, 12, 31)]
        past = past_sessions[-160:]
        future = upcoming[:10]
        current = sessions[sessions.year == year]
        window = past.append(current).append(future)
        frames = []
        for yy in (year - 1, year, year + 1):
            frame = cache[yy]
            relevant = frame.loc[frame.date.isin(window)].copy()
            frames.append(relevant)
        joined = pd.concat(frames, ignore_index=True)
        if joined.duplicated(["ticker", "date"]).any():
            raise ValueError(f"Duplicate security/date in {year}")
        panel = build_panel(joined, window)
        total_signal_bars += int(panel.date.dt.year.eq(year).sum())
        daily.extend(_daily_cohorts(panel, year, min_turnover, min_price, min_names, top_k, embargo))
        # Keep only next year's context to limit peak RAM.
        for yy in list(cache):
            if yy < year:
                del cache[yy]
        del frames, joined, panel
        print(json.dumps({"year": year, "daily_factor_records": len(daily),
                          "bars_examined_to_date": total_signal_bars}), flush=True)
    daily_df = pd.DataFrame(daily)
    results, selection, study = summarize(daily_df, roundtrip_bps)
    dest.mkdir(parents=True, exist_ok=True)
    results.to_csv(dest / "kswing_factor_results_v03.csv", index=False)
    selection.to_csv(dest / "kswing_training_selection_v03.csv", index=False)
    study.update({
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "source_snapshot": "FinanceData/marcap @ 94c138df4bf7376be8d28f979edb14020e2a547a",
        "years": "2019-2025, with 2018/2026 context",
        "source_calendar_observed_sessions": len(sessions),
        "calendar_discrepancy": cal_report,
        "signal_bars_examined": total_signal_bars,
        "daily_factor_records": len(daily_df),
        "filters_known_at_signal": {
            "min_turnover_krw": min_turnover, "min_close_krw": min_price,
            "min_factor_cross_section": min_names, "top_k": top_k,
        },
        "non_tunable_splits": "train 2019-2022, valid 2023, test 2024-2025, 10-session embargo at regime boundaries",
        "refuse_certification": True,
        "all_output_excludes_tickers_and_raw_market_prices": True,
    })
    (dest / "kswing_research_summary_v03.json").write_text(
        json.dumps(study, ensure_ascii=False, indent=2), encoding="utf-8")
    output = {
        "status": "REAL_DATA_EXPLORATORY_RESULTS_NOT_BACKTEST",
        "test_selected": results.loc[(results.split == "test") & results.preselected_using_train_only,
                                      ["horizon", "factor", "signal_days", "mean_daily_rank_ic", "topk_avg_excess_gross"]].round(6).to_dict("records"),
        "factor_groups": len(results), "daily_evaluations": len(daily_df),
    }
    print(json.dumps(output, ensure_ascii=False), flush=True)
    return output


def main():
    parser = argparse.ArgumentParser(description="Validate 18 factors against real quarantined KRX-derived prices")
    parser.add_argument("--data", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--min-turnover", type=float, default=100_000_000.)
    parser.add_argument("--min-close", type=float, default=1000.)
    parser.add_argument("--min-names", type=int, default=50)
    parser.add_argument("--top-k", type=int, default=10)
    parser.add_argument("--roundtrip-bps", type=float, default=20.)
    args = parser.parse_args()
    run(args.data, args.output, args.min_turnover, args.min_close,
        args.min_names, args.top_k, args.roundtrip_bps)


if __name__ == "__main__":
    main()
