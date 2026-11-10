"""v0.8 bounded research candidates: deterministic factor expressions, train-only.

This is an EXPERIMENT GENERATOR, not an automatic trading strategy.
Never read market returns or dates after 2022 for formula orientation/selection.
2023 is already inspected from previous projects; leave it unused here.
All expressions use observed T and earlier inputs from the causal v0.4 library.
"""
from __future__ import annotations
from dataclasses import dataclass
import numpy as np
import pandas as pd

BASE=(
    "ta__atr_wilder_pct_7",
    "ta__parkinson_vol_20",
    "ta__rsi_wilder_14",
    "ta__roc_20",
    "ta__relative_turnover_20",
    "ta__bb_bandwidth_20",
    "ta__ichi_tenkan_kijun_spread",
    "ta__macd_pct",
)
FEATURES=(
    "c01_low_vol_positive_momentum",
    "c02_low_vol_negative_momentum",
    "c03_oversold_low_vol",
    "c04_oversold_high_turnover",
    "c05_macd_low_vol",
    "c06_ichimoku_momentum",
    "c07_turnover_trend",
    "c08_low_vol_contraction",
    "c09_ichimoku_low_vol",
    "c10_oversold_macd",
    "c11_turnover_low_risk",
    "c12_price_strength_scaled_by_vol",
)


def candidate_expressions(frame: pd.DataFrame) -> pd.DataFrame:
    """Feature values calculated per security without any future return inputs.

    Inputs are already causal; normalizers use fixed published math, not
    sample-wide future standardization. Output is NOT a trade signal.
    """
    missing=set(BASE)-set(frame.columns)
    if missing:
        raise ValueError("missing causal factor columns: "+str(sorted(missing)))
    a,r,si,m,t,b,i,d=(pd.to_numeric(frame[x],errors="coerce").astype(float) for x in BASE)
    # Elementwise, deterministic, bounded nonlinearity. No future-sample mean.
    vol=(a.clip(lower=0)*100).clip(upper=30)
    risk=1/(1+vol)
    momentum=np.tanh(10*m)
    relative_volume=np.tanh(np.log(t.clip(lower=1e-6)))
    ichimoku=np.tanh(15*i)
    macd=np.tanh(50*d)
    oversold=((50-si)/50).clip(-1,1)
    squeeze=(1/(1+20*b.clip(lower=0))).clip(0,1)
    pvol=(1/(1+10*r.clip(lower=0))).clip(0,1)
    result=pd.DataFrame({
        FEATURES[0]:risk*momentum,
        FEATURES[1]:risk*(-momentum),
        FEATURES[2]:risk*oversold,
        FEATURES[3]:relative_volume*oversold,
        FEATURES[4]:risk*macd,
        FEATURES[5]:ichimoku*momentum,
        FEATURES[6]:relative_volume*momentum,
        FEATURES[7]:squeeze*pvol,
        FEATURES[8]:ichimoku*pvol,
        FEATURES[9]:macd*oversold,
        FEATURES[10]:relative_volume*risk,
        FEATURES[11]:momentum*pvol,
    },index=frame.index)
    return result.replace([np.inf,-np.inf],np.nan)


def daily_rank_ic(day: pd.DataFrame, factor: str, label: str,
                  min_names: int = 35) -> float:
    available=day[[factor,label]].dropna()
    if len(available)<min_names or available[factor].nunique()<3 or available[label].nunique()<3:
        return np.nan
    return float(available[factor].rank().corr(available[label].rank()))


def evaluate_train_only(panel: pd.DataFrame, *, horizon: int = 10,
                        min_daily_names: int = 35) -> tuple[pd.DataFrame,pd.DataFrame]:
    """Freeze direction in 2019-20; 2021-22 internal stability is descriptive.

    No 2023/2024/2025/2026 data allowed. All years have been inspected in older
    factor research and hence the internal 2021-22 slice is NOT pristine OOS.
    """
    if horizon not in (5,10):
        raise ValueError("only 5/10-session returns supported")
    if not {"date",f"forward_return_{horizon}",*FEATURES}.issubset(panel):
        raise ValueError("candidate input frame or target missing")
    x=panel.copy()
    x["date"]=pd.to_datetime(x.date,errors="raise").dt.normalize()
    if x.date.isna().any() or x.date.dt.year.max()>2022 or x.date.dt.year.min()<2019:
        raise ValueError("holdout periods are locked; only training 2019-2022")
    label=f"forward_return_{horizon}"
    byday=[]
    for date,day in x.groupby("date",sort=True):
        for factor in FEATURES:
            value=daily_rank_ic(day,factor,label,min_daily_names)
            if np.isfinite(value):
                byday.append({"date":date,"year":date.year,"horizon":horizon,
                              "factor":factor,"rank_ic_raw":float(value)})
    daily=pd.DataFrame(byday)
    if daily.empty:
        raise ValueError("no valid daily factor cross sections")
    discovery=daily.loc[daily.year.isin((2019,2020))]
    internal=daily.loc[daily.year.isin((2021,2022))]
    if discovery.empty or internal.empty:
        raise ValueError("internal training split incomplete")
    stats=discovery.groupby("factor").rank_ic_raw.agg(["mean","count"])
    stats=stats.rename(columns={"mean":"discovery_raw_ic","count":"discovery_days"})
    stats["train_direction"]=np.where(stats.discovery_raw_ic.ge(0),1,-1)
    if not set(FEATURES).issubset(stats.index):
        raise ValueError("some candidates lack discovery samples; cannot compare")
    c=daily.merge(stats.reset_index(),on="factor",validate="many_to_one")
    c["oriented_ic"]=c.rank_ic_raw*c.train_direction
    grouped=c.groupby(["factor","year"],as_index=False).agg(
        signal_days=("oriented_ic","size"),mean_oriented_ic=("oriented_ic","mean")
    )
    train_period=c.groupby(["factor","train_direction"],as_index=False).agg(
        discovery_oriented_ic=("oriented_ic",lambda y: float(y.loc[c.loc[y.index,"year"].isin((2019,2020))].mean())),
        internal_2021_22_oriented_ic=("oriented_ic",lambda y: float(y.loc[c.loc[y.index,"year"].isin((2021,2022))].mean())),
        total_observation_days=("oriented_ic","size"),
    )
    train_period["positive_in_both_training_subperiods"]=(
        train_period.discovery_oriented_ic.gt(0)&train_period.internal_2021_22_oriented_ic.gt(0))
    train_period["not_independent_confirmation"]=True
    return grouped,train_period.sort_values(
        ["positive_in_both_training_subperiods","internal_2021_22_oriented_ic"],
        ascending=[False,False]).reset_index(drop=True)
