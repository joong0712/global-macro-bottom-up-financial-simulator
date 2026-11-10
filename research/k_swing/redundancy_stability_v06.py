"""v0.6 training-only duplicate screening + year-by-year factor stability.

198? No: 170 broad + 18 original = 188 named numerical variants.
Only 2019-22 data can select factor families/cluster representatives.
2023 is a *previously inspected* exploratory year, never independent holdout.
2024-2026 are not opened. No price or security-level data are published.
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from .factor_matrix_v04 import one_symbol_matrix
from .factor_pilot_v04 import _load_sample
from .data import load_calendar

TRAIN_END = 2022
EXPLORATORY_END = 2023
MAX_YEAR = 2023
HORIZONS = (5, 10)


def correlated_clusters(
    training: pd.DataFrame,
    features: list[str],
    train_rank: pd.DataFrame,
    threshold: float = 0.95,
    every_nth_session: int = 5,
    min_pairwise_bars: int = 250,
) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    """Within-date percentile normalization avoids mistaking price level for alpha.

    Compute correlations on TRAINING only. Absolute correlation joins opposite
    as well as same-direction variants; connected components can be transitive
    and do not imply every pair in a component exceeds the threshold.
    """
    if not .5 <= threshold < 1 or every_nth_session < 1 or min_pairwise_bars < 3:
        raise ValueError("invalid duplicate-screen parameters")
    if training.date.dt.year.max() > TRAIN_END:
        raise ValueError("Future data leaked into training factor correlations")
    if not features or len(set(features)) != len(features):
        raise ValueError("require unique training factors")
    if not set(features).issubset(training):
        raise ValueError("feature columns absent")
    sessions = pd.DatetimeIndex(sorted(training.date.dropna().unique()))[::every_nth_session]
    sample = training.loc[training.date.isin(sessions)]
    if sample.empty:
        raise ValueError("no training observations")
    # Each date ranked *without* looking at a future return label.
    normalized = sample.groupby("date", sort=False)[features].rank(pct=True)
    corr = normalized.corr(method="pearson", min_periods=min_pairwise_bars)
    parent = {f:f for f in features}

    def find(a):
        while parent[a]!=a:
            parent[a]=parent[parent[a]]
            a=parent[a]
        return a

    def union(a,b):
        ra,rb=find(a),find(b)
        if ra!=rb:
            parent[max(ra,rb)] = min(ra,rb)

    edges=[]
    for i,a in enumerate(features):
        for b in features[i+1:]:
            coefficient = corr.loc[a,b]
            if pd.notna(coefficient) and abs(coefficient)>=threshold:
                union(a,b)
                edges.append({"feature_1":a,"feature_2":b,
                              "train_abs_rank_correlation":float(abs(coefficient)),
                              "train_signed_rank_correlation":float(coefficient)})
    rank_weights = train_rank.groupby("factor").train_rank_ic.apply(
        lambda z: float(z.abs().max())
    ).to_dict()
    members={}
    for f in features:
        members.setdefault(find(f),[]).append(f)
    rows=[]
    for index,(_,group) in enumerate(sorted(members.items(),key=lambda a:min(a[1])),start=1):
        representative = sorted(group,key=lambda f:(-rank_weights.get(f,0),f))[0]
        for f in sorted(group):
            rows.append({
                "cluster":index,"feature":f,
                "representative_selected_from_training_only":representative,
                "cluster_members":len(group),
                "representative":bool(f==representative),
                "available_training_rank_ic_abs":rank_weights.get(f,np.nan),
            })
    report = {
        "feature_count":len(features),"cluster_count":len(members),
        "redundant_variants":len(features)-len(members),
        "positive_negative_edges":len(edges),
        "threshold_abs_within_date_rank_corr":threshold,
        "train_sampling_every_nth_session":every_nth_session,
        "sampled_training_dates":len(sessions),
        "sampled_training_ticker_days":len(sample),
        "no_2023_or_later_used_for_cluster_selection":True,
        "clustering_warning":"connected components are not maximal cliques; no predictive-alpha significance is implied",
    }
    return pd.DataFrame(rows),pd.DataFrame(edges,columns=[
        "feature_1","feature_2","train_abs_rank_correlation","train_signed_rank_correlation",
    ]),report


def fast_spearman_vector(day: pd.DataFrame, features: list[str],
                         label: str, min_names: int = 25) -> dict[str,float]:
    """Per-date cross-sectional Spearman with pairwise-valid observations."""
    y=day[label]
    okay=y.notna()
    if okay.sum()<min_names:
        return {}
    x=day.loc[okay,features].rank()
    target=y.loc[okay].rank().to_numpy(float)
    mat=x.to_numpy(float)
    mask=np.isfinite(mat)
    n=mask.sum(axis=0).astype(float)
    clean=np.where(mask,mat,0.)
    ty=target[:,None]
    sx=clean.sum(axis=0)
    sy=(ty*mask).sum(axis=0)
    sxx=(clean*clean).sum(axis=0)
    syy=((ty*ty)*mask).sum(axis=0)
    sxy=(clean*ty).sum(axis=0)
    num=n*sxy-sx*sy
    denominator=np.sqrt(np.maximum(0,n*sxx-sx*sx)*np.maximum(0,n*syy-sy*sy))
    corr=np.divide(num,denominator,out=np.full(len(features),np.nan),
                   where=(n>=min_names)&(denominator>0))
    return {f:float(v) for f,v in zip(features,corr) if np.isfinite(v)}


def year_by_year_ic(panel: pd.DataFrame, train_rank: pd.DataFrame,
                    n_train_candidates: int = 15) -> tuple[pd.DataFrame,pd.DataFrame]:
    """Annual IC for factors preselected from train 2019-22 only."""
    if panel.date.dt.year.max()>EXPLORATORY_END:
        raise ValueError("2024+ dates must not enter yearly analysis")
    if n_train_candidates<1:
        raise ValueError("n_train_candidates must be positive")
    chosen=train_rank.sort_values(["horizon","train_rank"]).groupby(
        "horizon",sort=False).head(n_train_candidates)
    record=[]
    for horizon in HORIZONS:
        sub=chosen.loc[chosen.horizon.eq(horizon)]
        factors=sub.factor.to_list()
        directions=dict(zip(sub.factor,sub.direction))
        label=f"forward_return_{horizon}"
        for date,day in panel.groupby("date",sort=True):
            corr=fast_spearman_vector(day,factors,label,min_names=25)
            for f,v in corr.items():
                record.append({
                    "date":pd.Timestamp(date),"year":pd.Timestamp(date).year,
                    "horizon":horizon,"factor":f,
                    "oriented_ic":v*int(directions[f]),
                })
    daily=pd.DataFrame(record)
    if daily.empty:
        raise ValueError("no annual IC rows")
    annual=daily.groupby(["horizon","factor","year"],as_index=False).agg(
        days=("oriented_ic","size"),
        mean_oriented_ic=("oriented_ic","mean"),
        positive_day_fraction=("oriented_ic",lambda x:(x>0).mean()),
        ic_daily_sd=("oriented_ic","std"),
    )
    if any(annual.year>2023):
        raise AssertionError("held-out year violated")
    if not (set(annual.year)&{2019,2020,2021,2022}):
        raise ValueError("train years absent")
    flags=[]
    for (h,f),group in annual.groupby(["horizon","factor"],sort=True):
        train=group.loc[group.year.le(2022)].set_index("year")
        val=group.loc[group.year.eq(2023)]
        flags.append({
            "horizon":int(h),"factor":f,
            "train_years_with_evidence":int(len(train)),
            "positive_train_years":int(train.mean_oriented_ic.gt(0).sum()),
            "mean_2019_22_yearly_ic":float(train.mean_oriented_ic.mean()),
            "sd_2019_22_yearly_ic":float(train.mean_oriented_ic.std(ddof=1)),
            "exploratory_2023_ic":float(val.mean_oriented_ic.iloc[0]) if len(val) else np.nan,
            "stable_sign_all_available_train_years":bool(train.mean_oriented_ic.gt(0).all()),
            "positive_2023_reused":bool(len(val) and val.mean_oriented_ic.iloc[0]>0),
            "not_significance_test":True,
        })
    return annual,pd.DataFrame(flags)


def run(data_dir: Path, historical_ranks: Path, output: Path,
        modulus: int = 16, rank_candidates: int = 15) -> dict:
    """Reads 2017-23 PRIVATE data only; outputs aggregate factor statistics."""
    q=json.loads((data_dir/"market_structure_quality.json").read_text(encoding="utf-8"))
    cal=q.get("calendar",{})
    if cal.get("reference_only_dates") or cal.get("observed_only_dates"):
        raise ValueError("unresolved market calendar mismatch")
    private=data_dir/"_private"
    sampled=_load_sample(private,modulus)
    sessions=load_calendar(private/"krx_observed_sessions.csv",sampled)
    if sessions.max().year>2023:
        raise ValueError("2026 confirmation period locked")
    training_ranks=pd.read_csv(historical_ranks)
    if set(training_ranks.horizon)!={5,10} or training_ranks.duplicated(["horizon","factor"]).any():
        raise ValueError("invalid previous-training ranks")
    feature_names=None
    parts=[]
    for ticker,source in sampled.groupby("ticker",sort=True):
        mat=one_symbol_matrix(source,sessions,"2019-01-01","2023-12-31")
        if mat.empty:
            continue
        if feature_names is None:
            feature_names=[f for f in mat if f.startswith("legacy__") or f.startswith("ta__")]
        context=source[["date","ticker","close","turnover","volume","unsafe_session"]]
        mat=mat.merge(context,on=["date","ticker"],validate="one_to_one")
        eligible=mat.close.ge(1000)&mat.turnover.ge(100_000_000)&mat.volume.gt(0)&~mat.unsafe_session.fillna(True)
        mat=mat.loc[eligible,["date","ticker",*feature_names,"forward_return_5","forward_return_10"]]
        if not mat.empty:
            mat.loc[:,feature_names]=mat[feature_names].astype("float32")
            parts.append(mat)
    if not parts:
        raise ValueError("no eligible samples")
    panel=pd.concat(parts,ignore_index=True)
    if panel.date.dt.year.max()>2023:
        raise AssertionError("locked time period")
    # 2023 is excluded entirely from redundancy representative selection.
    clusters,edges,cluster_report=correlated_clusters(
        panel.loc[panel.date.dt.year<=2022],feature_names,training_ranks)
    annual,flags=year_by_year_ic(panel,training_ranks,rank_candidates)
    output.mkdir(parents=True,exist_ok=True)
    clusters.to_csv(output/"training_only_feature_clusters.csv",index=False)
    edges.to_csv(output/"training_only_high_correlation_edges.csv",index=False)
    annual.to_csv(output/"factor_annual_rank_ic_2019_2023.csv",index=False)
    flags.to_csv(output/"training_selected_yearly_stability.csv",index=False)
    report={
        "status":"EXPLORATORY_TIME_STABILITY_AND_TRAINING_CORRELATION_DIAGNOSTICS",
        "created_utc":datetime.now(timezone.utc).isoformat(),
        "source":"FinanceData/marcap pinned v0.4 snapshot",
        "sample_modulus":modulus,
        "sample_ticker_codes":int(panel.ticker.nunique()),
        "sample_signal_days":int(panel.date.nunique()),
        "sample_signal_ticker_days":int(len(panel)),
        "indicator_count":len(feature_names),
        "annual_stability_factor_horizon_tests":int(len(flags)),
        "cluster_stats":cluster_report,
        "years":[2019,2020,2021,2022,2023],
        "2023_status":"REUSED exploratory validation, not independent",
        "2024_2025_2026_opened":False,
        "significance":"NOT_ESTIMATED; yearly sign test is descriptive and 5/10-day forward returns overlap",
        "limitations":[
            "Only deterministic hash subset; market and sector may confound",
            "2019-2022 same period used for factor selection and redundancy representatives",
            "No official corporate action or delisted universe certification",
            "Collinear variants are not independent hypotheses",
            "No portfolio PnL, capital accounting or live fills",
        ]
    }
    (output/"v06_redundancy_stability_manifest.json").write_text(
        json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps({
        "status":report["status"],"symbols":report["sample_ticker_codes"],
        "features":len(feature_names),"clusters":cluster_report["cluster_count"],
        "annual_records":len(annual),"flag_records":len(flags),
        "locked_2026":True},ensure_ascii=False),flush=True)
    return report


def main():
    p=argparse.ArgumentParser(description="v0.6 training redundancy and yearly IC (no 2026)")
    p.add_argument("--data",type=Path,required=True)
    p.add_argument("--training-ranks",type=Path,required=True)
    p.add_argument("--output",type=Path,required=True)
    p.add_argument("--modulus",type=int,default=16)
    args=p.parse_args()
    run(args.data,args.training_ranks,args.output,args.modulus)


if __name__=="__main__":
    main()
