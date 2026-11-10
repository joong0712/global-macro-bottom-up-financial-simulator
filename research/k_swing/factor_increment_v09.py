"""v0.9 matched-universe incremental indicator test: 2019-2022 TRAIN only.

Compares candidate expressions to ATR & Parkinson on EXACTLY the SAME
ticker/date/forward-label observations and tests residual cross-sectional
association after both volatility controls. This is exploratory: the 2019-22
period was already inspected, and official delisted/adjusted prices are absent.

No 2023-2026 data, no stock picks or live trade signals.
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from .candidate_research_v08 import BASE, FEATURES, candidate_expressions
from .candidate_train_eval_v08 import train_data
from .data import load_calendar
from .factor_matrix_v04 import one_symbol_matrix

BASELINES = ("ta__atr_wilder_pct_7", "ta__parkinson_vol_20")
HORIZONS = (5, 10)
DISCOVERY_YEARS = (2019, 2020)
INTERNAL_YEARS = (2021, 2022)
BLOCK_SIZE = 20
BOOTSTRAP_REPS = 500
MIN_NAMES = 35


def matched_day_metrics(day: pd.DataFrame, candidate: str, label: str,
                        min_names: int = MIN_NAMES) -> dict | None:
    """Same pairwise-complete stock cross-section for candidate and baselines.

    Return raw rank ICs, residual IC after both baseline rank signals are
    controlled, and the total matched securities count. Never condition
    which security is selected on the return value.
    """
    fields = [candidate, *BASELINES, label]
    if not set(fields).issubset(day.columns):
        raise ValueError("candidate, baselines and forward label required")
    good = day[fields].replace([np.inf, -np.inf], np.nan).dropna()
    n = len(good)
    if n < min_names or good[label].nunique() < 3 or any(good[c].nunique() < 3 for c in fields[:-1]):
        return None
    rank = good.rank(method="average", pct=True)
    arr = rank.to_numpy(float)
    x, a, p, y = (arr[:, k] for k in range(4))
    def corr(u, v):
        if np.std(u) <= 1e-10 or np.std(v) <= 1e-10:
            return np.nan
        return float(np.corrcoef(u, v)[0, 1])
    design = np.column_stack([np.ones(n), a, p])
    if np.linalg.matrix_rank(design, tol=1e-8) < 3:
        partial = np.nan  # Cannot claim independent contribution in a degenerate cohort.
    else:
        xx = x - design @ np.linalg.lstsq(design, x, rcond=None)[0]
        yy = y - design @ np.linalg.lstsq(design, y, rcond=None)[0]
        partial = corr(xx, yy)
    return {
        "matched_stocks": n,
        "candidate_raw_ic": corr(x, y),
        "atr_lowvol_ic": -corr(a, y),  # ATR/Parkinson train-favorable low orientation.
        "parkinson_lowvol_ic": -corr(p, y),
        "candidate_partial_ic_given_both_vol_controls": partial,
        "candidate_vs_atr_raw_delta": np.nan,  # set after discovery orientation
        "candidate_vs_parkinson_raw_delta": np.nan,
    }


def circular_block_ci(values: np.ndarray, block: int = BLOCK_SIZE,
                      draws: int = BOOTSTRAP_REPS, seed: int = 609) -> tuple[float, float]:
    """Descriptive moving-block percentile CI, not confirmatory p-value."""
    x = np.asarray(values, dtype=float)
    if x.ndim != 1 or len(x) < block * 2 or draws < 100 or block < 2:
        raise ValueError("insufficient daily paired data for block diagnostic")
    if not np.isfinite(x).all():
        raise ValueError("missing pairwise IC values")
    rng = np.random.default_rng(seed)
    k = int(np.ceil(len(x) / block))
    samples = np.empty(draws, dtype=float)
    for j in range(draws):
        starts = rng.integers(len(x), size=k)
        indices = (starts[:, None] + np.arange(block)[None, :]) % len(x)
        samples[j] = float(x[indices.reshape(-1)[:len(x)]].mean())
    return tuple(float(t) for t in np.quantile(samples, [.025, .975]))


def assess_daily(daily: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Freeze candidate sign AND comparison baseline in 2019-2020 only."""
    if daily.empty:
        raise ValueError("no daily pairs")
    x=daily.copy()
    x["date"]=pd.to_datetime(x.date,errors="raise").dt.normalize()
    if x.date.isna().any() or x.date.dt.year.max()>2022 or x.date.dt.year.min()<2019:
        raise ValueError("2023-2026 held-out research periods are locked")
    if x.duplicated(["date","candidate","horizon"]).any():
        raise ValueError("duplicate paired observations")
    if set(x.horizon)!={5,10}:
        raise ValueError("expected both precommitted return horizons")
    x["year"] = x.date.dt.year
    discovery=x.loc[x.year.isin(DISCOVERY_YEARS)]
    internal=x.loc[x.year.isin(INTERNAL_YEARS)]
    if discovery.empty or internal.empty:
        raise ValueError("missing discovery or internal training period")
    decisions=[]
    for (name,h),g in discovery.groupby(["candidate","horizon"],sort=True):
        if len(g)<150:
            raise ValueError("too few discovery signal days to lock factors")
        sign=1 if g.candidate_raw_ic.mean()>=0 else -1
        baseline_ic={
            BASELINES[0]:float(g.atr_lowvol_ic.mean()),
            BASELINES[1]:float(g.parkinson_lowvol_ic.mean()),
        }
        winner=max(BASELINES,key=lambda z:(baseline_ic[z], z))
        decisions.append({
            "candidate":name,"horizon":int(h),"candidate_discovery_direction":sign,
            "baseline_preselected_2019_20":winner,
            "baseline_discovery_2019_20_ic":baseline_ic[winner],
            "discovery_signal_days":len(g),
        })
    decisions=pd.DataFrame(decisions)
    x=x.merge(decisions,on=["candidate","horizon"],how="inner",validate="many_to_one")
    if len(x)!=len(daily):
        raise ValueError("missing one or more candidate discovery rules")
    x["candidate_oriented_ic"]=x.candidate_raw_ic*x.candidate_discovery_direction
    x["candidate_oriented_partial_ic"]=(
        x.candidate_partial_ic_given_both_vol_controls*x.candidate_discovery_direction)
    x["selected_baseline_oriented_ic"]=np.where(
        x.baseline_preselected_2019_20.eq(BASELINES[0]),
        x.atr_lowvol_ic,x.parkinson_lowvol_ic)
    x["paired_incremental_ic"]=x.candidate_oriented_ic-x.selected_baseline_oriented_ic
    x["discovery_or_internal"]=np.where(x.year.isin(DISCOVERY_YEARS),
                                       "discovery_2019_20","internal_2021_22")
    yearly=x.groupby(["candidate","horizon","year"],as_index=False).agg(
        signal_days=("paired_incremental_ic","size"),
        matched_stocks_mean=("matched_stocks","mean"),
        candidate_oriented_ic=("candidate_oriented_ic","mean"),
        paired_baseline_oriented_ic=("selected_baseline_oriented_ic","mean"),
        paired_ic_improvement=("paired_incremental_ic","mean"),
        partial_ic_both_vol_controls=("candidate_oriented_partial_ic","mean"),
    )
    reports=[]
    for (name,h,period),g in x.groupby(["candidate","horizon","discovery_or_internal"],sort=True):
        g=g.sort_values("date")
        rec={
            "candidate":name,"horizon":int(h),"period":period,
            "signal_days":len(g),
            "matched_stock_days":int(g.matched_stocks.sum()),
            "direction_frozen_in_2019_20":int(g.candidate_discovery_direction.iloc[0]),
            "baseline_frozen_in_2019_20":str(g.baseline_preselected_2019_20.iloc[0]),
            "candidate_oriented_rank_ic":float(g.candidate_oriented_ic.mean()),
            "baseline_oriented_rank_ic_same_names":float(g.selected_baseline_oriented_ic.mean()),
            "paired_mean_ic_improvement":float(g.paired_incremental_ic.mean()),
            "partial_ic_given_both_baselines":float(g.candidate_oriented_partial_ic.mean()),
            "partial_ic_days":int(g.candidate_oriented_partial_ic.notna().sum()),
        }
        for metric in ("paired_incremental_ic","candidate_oriented_partial_ic"):
            sub=g[metric].dropna().to_numpy(float)
            if len(sub)<BLOCK_SIZE*2:
                low=high=np.nan
            else:
                low,high=circular_block_ci(sub,seed=609+int(h))
            rec[f"{metric}_block95_low"]=low
            rec[f"{metric}_block95_high"]=high
        rec["not_independent_out_of_sample"]=True
        reports.append(rec)
    return pd.DataFrame(reports),yearly


def run(data_dir:Path,output_dir:Path,modulus:int=16)->dict:
    """2017-2022 source ONLY. Never loads 2023-2026 forward outcomes."""
    if modulus<1:raise ValueError("invalid sample modulus")
    check=json.loads((data_dir/"market_structure_quality.json").read_text())
    cal=check.get("calendar",{})
    if cal.get("reference_only_dates") or cal.get("observed_only_dates"):
        raise ValueError("unexpected market-calendar mismatch")
    data=train_data(data_dir/"_private",modulus)
    sessions=load_calendar(data_dir/"_private"/"krx_observed_sessions.csv",data)
    if sessions.max().year>2022:
        raise ValueError("2023 and later source not allowed for candidate comparisons")
    # Don't use 2022 year-end future labels to select an apparently strong signal.
    embargo=sessions[sessions.year==2022][-10:]
    records=[]
    for ticker,prices in data.groupby("ticker",sort=True):
        mat=one_symbol_matrix(prices,sessions,"2019-01-01","2022-12-31")
        if mat.empty:continue
        context=prices[["date","ticker","close","turnover","volume","unsafe_session"]]
        mat=mat.merge(context,on=["date","ticker"],how="left",validate="one_to_one")
        valid=(mat.close.ge(1000)&mat.turnover.ge(100_000_000)&mat.volume.gt(0)&
               ~mat.unsafe_session.fillna(True)&~mat.date.isin(embargo))
        usable=mat.loc[valid]
        if usable.empty:continue
        combos=candidate_expressions(usable)
        q=pd.concat([usable[["date","forward_return_5","forward_return_10",*BASELINES]
                               ].reset_index(drop=True),combos.reset_index(drop=True)],axis=1)
        records.append(q)
    if not records:raise ValueError("no screened historical candidate panel")
    panel=pd.concat(records,ignore_index=True)
    if panel.date.dt.year.max()>2022:raise AssertionError("future signal leakage")
    metrics=[]
    for dt,day in panel.groupby("date",sort=True):
        for h in HORIZONS:
            target=f"forward_return_{h}"
            for name in FEATURES:
                vals=matched_day_metrics(day,name,target)
                if vals is not None and np.isfinite(vals["candidate_raw_ic"]):
                    metrics.append({"date":dt,"candidate":name,"horizon":h,**vals})
    if not metrics:raise ValueError("no eligible matched daily factor comparisons")
    summaries,annual=assess_daily(pd.DataFrame(metrics))
    output_dir.mkdir(parents=True,exist_ok=True)
    summaries.to_csv(output_dir/"v09_same_stock_incremental_ic.csv",index=False)
    annual.to_csv(output_dir/"v09_matched_yearly_ic.csv",index=False)
    meta={
        "status":"DESCRIPTIVE_MATCHED_BASELINE_COMPARISON_NOT_PROFIT_VALIDATION",
        "created_utc":datetime.now(timezone.utc).isoformat(),
        "candidate_formulas_evaluated":len(FEATURES),"factor_horizon_tests":len(FEATURES)*len(HORIZONS),
        "historical_eligible_signal_days":int(panel.date.nunique()),
        "history_from_2017_to_2022_only":True,
        "candidate_orientation_and_baseline_selection":"2019-2020 discovery only",
        "internal_evaluation":"2021-2022 (previously inspected, not pristine holdout)",
        "annual_same_stock_pairwise_rank_ic":True,
        "partial_rank_ic_controls":list(BASELINES),
        "block_sessions":BLOCK_SIZE,
        "bootstrap_repetitions":BOOTSTRAP_REPS,
        "no_actual_fills_or_verified_adjusted_prices":True,
        "2023_2024_2025_2026_not_read":True,
        "known_research_limits":[
            "An IC delta is not an incremental realized stock-trading profit",
            "12 candidates use overlapping original inputs; some have exact sign mirrors",
            "Paired day sample uses only ticker-days with future labels observable; missing returns can induce selection bias",
            "2019-22 years previously inspected in baseline study: no pristine out-of-sample verification",
            "No certified corporate-action adjustments, delisted ordinary-share reference, sector neutrality, or tax/actual auction fills",
            "20-session block-bootstrap is descriptive and no selective-inference correction is claimed",
        ],
    }
    (output_dir/"v09_incremental_manifest.json").write_text(
        json.dumps(meta,ensure_ascii=False,indent=2),encoding="utf-8")
    vals=summaries.loc[summaries.period.eq("internal_2021_22")].sort_values(
        ["horizon","paired_mean_ic_improvement"],ascending=[True,False])
    print(json.dumps({"status":meta["status"],"matched_factor_days":len(metrics),
                      "internal_candidates_positive_incremental_ic":
                      int(vals.paired_mean_ic_improvement.gt(0).sum()),
                      "2026_holdout_locked":True,
                      "best_retrospective_internal_examples":
                      vals.groupby("horizon").head(3)[
                          ["candidate","horizon","paired_mean_ic_improvement","partial_ic_given_both_baselines"]
                      ].round(5).to_dict("records")},ensure_ascii=False),flush=True)
    return meta


def main():
    p=argparse.ArgumentParser(description="v0.9 paired factor/ATR/Parkinson IC, training only")
    p.add_argument("--data",required=True,type=Path)
    p.add_argument("--output",required=True,type=Path)
    p.add_argument("--modulus",type=int,default=16)
    args=p.parse_args()
    run(args.data,args.output,args.modulus)


if __name__=="__main__":
    main()
