"""v0.7 exploratory statistical skepticism: blocks, correlated factors and FDR.

Selected factor directions are from 2019-22 training ONLY. Reused 2023 daily
cross-sectional IC measures are NOT a fresh holdout. Signals overlap: 20-day
block procedures are sensitivity diagnostics, not a proof of profitable alpha.
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

HOLDOUT_EXCLUSION = (2024, 2025, 2026)
MIN_DAILY_NAMES = 25


def bh_qvalues(pvalues: np.ndarray) -> np.ndarray:
    """Benjamini-Hochberg step-up adjustment, stable to equal p-values."""
    p = np.asarray(pvalues, float)
    if p.ndim != 1 or not len(p) or np.any(~np.isfinite(p)) or np.any((p<0)|(p>1)):
        raise ValueError("pvalues must be a finite 1D 0-to-1 vector")
    order = np.argsort(p, kind="stable")
    ranks = np.arange(1, len(p)+1)
    adjusted = np.minimum.accumulate((p[order] * len(p) / ranks)[::-1])[::-1]
    result = np.empty_like(p)
    result[order] = np.minimum(adjusted, 1.)
    return result


def block_diagnostics(
    daily_ic: pd.DataFrame,
    *,
    n_iter: int = 750,
    block_sessions: int = 20,
    seed: int = 16421,
) -> pd.DataFrame:
    """Block-resampling CIs, common sign-flip null, BH and max-statistics.

    Strong assumption for sign-flip null: joint distribution of 20-session IC
    blocks is symmetric under sign reversal. For overlapping forward returns
    and already-inspected selection, this is an *exploratory* null only.
    """
    required={"date","factor","horizon","oriented_ic"}
    if not required.issubset(daily_ic.columns) or daily_ic.empty:
        raise ValueError("daily factor IC panel required")
    x=daily_ic.copy()
    x["date"]=pd.to_datetime(x.date).dt.normalize()
    if set(x.date.dt.year)!={2023}:
        raise ValueError("only the previously inspected 2023 exploratory dates permitted")
    if x.duplicated(["date","factor","horizon"]).any():
        raise ValueError("duplicate panel records")
    if n_iter<100 or block_sessions<5:
        raise ValueError("insufficient bootstrap iterations or block length")
    dates=pd.DatetimeIndex(sorted(x.date.unique()))
    x["key"]=x.horizon.astype(str)+"d__"+x.factor
    pivot=x.pivot(index="date",columns="key",values="oriented_ic").reindex(dates)
    if pivot.shape[1]<2 or pivot.shape[0]<block_sessions*3:
        raise ValueError("insufficient factors/sessions for blocked statistics")
    mat=pivot.to_numpy(float)
    n=len(mat)
    observed=np.nanmean(mat,axis=0)
    if (~np.isfinite(observed)).any():
        raise ValueError("factor has no valid observations")
    rng=np.random.default_rng(seed)
    bs=np.empty((n_iter,len(observed)))
    null=np.empty((n_iter,len(observed)))
    for rep in range(n_iter):
        # Circular moving block bootstrap preserves local serial dependence.
        starts=rng.integers(n,size=int(np.ceil(n/block_sessions)))
        sample=np.concatenate([(np.arange(block_sessions)+i)%n for i in starts])[:n]
        bs[rep]=np.nanmean(mat[sample],axis=0)
        # One shared sign per consecutive time block across all factors.
        # This preserves factor cross-dependence within the assumed null.
        flipped=mat.copy()
        for start in range(0,n,block_sessions):
            sign=rng.choice((-1.,1.))
            flipped[start:start+block_sessions]*=sign
        null[rep]=np.nanmean(flipped,axis=0)
    p=(1 + (null>=observed).sum(axis=0))/(n_iter+1)
    # The max of null factor means controls a single-family simultaneous test
    # only under the strong sign symmetry assumption, not automatic FWER proof.
    max_null=np.nanmax(null,axis=1)
    family_p=(1+(max_null[:,None]>=observed[None,:]).sum(axis=0))/(n_iter+1)
    q=bh_qvalues(p)
    result=[]
    for col,key in enumerate(pivot.columns):
        horizon,name=key.split("d__",1)
        result.append({
            "horizon":int(horizon),"factor":name,
            "n_daily_ic":int(pivot.iloc[:,col].notna().sum()),
            "mean_oriented_ic":float(observed[col]),
            "block_bootstrap_ci95_low":float(np.quantile(bs[:,col],.025)),
            "block_bootstrap_ci95_high":float(np.quantile(bs[:,col],.975)),
            "block_signflip_exploratory_p":float(p[col]),
            "bh_exploratory_q":float(q[col]),
            "max_factor_signflip_exploratory_p":float(family_p[col]),
            "assumed_block_sessions":block_sessions,
            "not_independent_confirmation":True,
        })
    return pd.DataFrame(result).sort_values(["horizon","factor"])


def real_run(data_dir: Path, training_file: Path, output_dir: Path, modulus: int = 16):
    """Never reads 2024-2026 or exports stock/security-level data."""
    if modulus<1:
        raise ValueError("invalid modulus")
    qa=json.loads((data_dir/"market_structure_quality.json").read_text())
    if qa.get("calendar",{}).get("reference_only_dates") or qa.get("calendar",{}).get("observed_only_dates"):
        raise ValueError("exchange calendar disagreement")
    sampled=_load_sample(data_dir/"_private",modulus)
    sessions=load_calendar(data_dir/"_private"/"krx_observed_sessions.csv",sampled)
    if sessions.max().year>2023:
        raise ValueError("2024-2026 holdout period opened")
    ranks=pd.read_csv(training_file)
    if ranks.duplicated(["factor","horizon"]).any() or set(ranks.horizon)!={5,10}:
        raise ValueError("invalid frozen training factor ranks")
    chosen=ranks.sort_values(["horizon","train_rank"]).groupby("horizon").head(15)
    factors=sorted(set(chosen.factor))
    sign={(int(row.horizon),row.factor):int(row.direction) for row in chosen.itertuples()}
    panels=[]
    for _,bars in sampled.groupby("ticker",sort=True):
        panel=one_symbol_matrix(bars,sessions,"2023-01-01","2023-12-31")
        if panel.empty:
            continue
        context=bars[["date","ticker","close","turnover","volume","unsafe_session"]]
        panel=panel.merge(context,on=["date","ticker"],validate="one_to_one")
        eligible=panel.close.ge(1000)&panel.turnover.ge(100_000_000)&panel.volume.gt(0)&~panel.unsafe_session.fillna(True)
        sub=panel.loc[eligible,["date",*factors,"forward_return_5","forward_return_10"]]
        if not sub.empty:
            panels.append(sub.astype({f:"float32" for f in factors}))
    if not panels:
        raise ValueError("no 2023 signal rows")
    joined=pd.concat(panels,ignore_index=True)
    # Last 10 signal dates of 2023 are embargoed as in earlier pilots.
    valid_sessions=sessions[sessions.year==2023]
    joined=joined.loc[~joined.date.isin(valid_sessions[-10:])]
    rows=[]
    for day,group in joined.groupby("date",sort=True):
        for horizon in (5,10):
            ycol=f"forward_return_{horizon}"
            for f in chosen.loc[chosen.horizon.eq(horizon),"factor"]:
                pair=group[[f,ycol]].dropna()
                if len(pair)<MIN_DAILY_NAMES or pair[f].nunique()<3 or pair[ycol].nunique()<3:
                    continue
                corr=pair[f].rank().corr(pair[ycol].rank())
                if np.isfinite(corr):
                    rows.append({"date":day,"horizon":horizon,"factor":f,
                                 "oriented_ic":float(corr)*sign[(horizon,f)]})
    agg=block_diagnostics(pd.DataFrame(rows))
    output_dir.mkdir(parents=True,exist_ok=True)
    agg.to_csv(output_dir/"v07_exploratory_block_fdr.csv",index=False)
    manifest={
        "status":"EXPLORATORY_SIGNFLIP_AND_BLOCK_FDR_ONLY",
        "created_utc":datetime.now(timezone.utc).isoformat(),
        "symbols":int(sampled.ticker.nunique()),
        "2023_eligible_security_signal_rows":len(joined),
        "factor_horizon_tests":len(agg),
        "daily_ic_records":len(rows),
        "block_sessions":20,
        "null_assumptions":"Joint 20-session sign symmetry, strong unverified assumption",
        "negative_controls":"No industry sectors, official split adjustment, full delisted universe or execution data",
        "2023_already_inspected":True,
        "pvalues_are_confirmatory":False,
        "2026_holdout_touched":False,
        "warning":"Multiple testing adjusted exploratory IC values cannot establish realized trading alpha"
    }
    (output_dir/"v07_statistical_manifest.json").write_text(
        json.dumps(manifest,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps({"status":manifest["status"],"symbol_codes":manifest["symbols"],
                      "tests":len(agg),"2026_locked":True}),flush=True)
    return manifest


def main():
    p=argparse.ArgumentParser(description="block-bootstrap BH/FDR, 2026 locked")
    p.add_argument("--data",type=Path,required=True)
    p.add_argument("--training-ranks",type=Path,required=True)
    p.add_argument("--output",type=Path,required=True)
    p.add_argument("--modulus",type=int,default=16)
    a=p.parse_args()
    real_run(a.data,a.training_ranks,a.output,a.modulus)


if __name__=="__main__":
    main()
