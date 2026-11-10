"""K-SWING v0.5: market/size-controlled IC and execution-friction diagnostics.

IMPORTANT:
- Existing v0.4 training-chosen VOLATILITY factors frozen in advance.
- 2019-2022 training and *already inspected* 2023 exploratory validation.
- 2024/25 are previously viewed. 2026 is locked, never read.
- The cost results are illustrative stress scenarios, NOT broker actual tax
  schedules, filled orders, portfolio returns or newly discovered alpha.
- Official point-in-time industry classification is NOT available here,
  so this phase DOES NOT claim sector neutralization.
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

# These 5 factors were already selected based on v0.4 historical training.
# Selection and direction are frozen. Do not tune on 2023 outcome.
FROZEN_LOW_VOL_FACTORS = (
    "ta__atr_wilder_pct_7",
    "ta__parkinson_vol_20",
    "ta__garman_klass_vol_20",
    "legacy__atr_pct_14",
    "ta__realized_vol_60",
)
HORIZONS = (5, 10)
TOP_K = (3, 10, 20)
COST_SCENARIOS_BPS = (20, 50, 100, 200)
TRAIN_YEARS = {2019, 2020, 2021, 2022}
EXPLORATORY_YEAR = 2023
FROZEN_DIRECTION = -1   # Low volatility was train-favorable.
MIN_ELIGIBLE = 40
MIN_STRATUM = 8


def read_yearly_size_market_data(data_dir: Path, years: tuple[int, ...]) -> pd.DataFrame:
    """Market/cap metadata at signal date T from raw marcap (NOT sector labels)."""
    parts = []
    for year in years:
        path = data_dir / "_raw" / f"marcap-{year}.parquet"
        if not path.is_file():
            raise FileNotFoundError(f"Missing private raw metadata: {path}")
        raw = pd.read_parquet(path)
        if "Date" not in raw.columns and raw.index.name == "Date":
            raw = raw.reset_index()
        need = {"Date", "Code", "Market", "Marcap"}
        if not need.issubset(raw.columns):
            raise ValueError(f"marcap lacks actual market-cap metadata: {need-set(raw.columns)}")
        s = raw.loc[:, ["Date", "Code", "Market", "Marcap"]].copy()
        s["date"] = pd.to_datetime(s.Date, errors="coerce").dt.normalize()
        s["ticker"] = s.Code.astype("string").str.strip()
        good = s.ticker.str.fullmatch(r"\d{1,6}").fillna(False)
        s = s.loc[good & s.date.dt.year.eq(year)].copy()
        s["ticker"] = s.ticker.str.zfill(6)
        market = s.Market.astype("string").str.strip().replace({
            "코스피":"KOSPI","코스닥":"KOSDAQ","유가증권":"KOSPI"
        })
        s = s.loc[market.isin(["KOSPI","KOSDAQ"])].copy()
        s["market"] = market.loc[s.index]
        s["market_cap_krw"] = pd.to_numeric(s.Marcap, errors="coerce")
        s = s.loc[s.market_cap_krw.gt(0), ["date","ticker","market","market_cap_krw"]]
        if s.duplicated(["date", "ticker"]).any():
            raise ValueError("Ambiguous ticker-day market capitalizations")
        parts.append(s)
        del raw
    if not parts:
        raise ValueError("No market/size metadata")
    return pd.concat(parts, ignore_index=True)


def assign_size_buckets(frame: pd.DataFrame, buckets: int = 3) -> pd.DataFrame:
    """Within same market and signal day, assign low/mid/high market-cap bucket."""
    if buckets < 2:
        raise ValueError("Need >=2 size buckets")
    required = {"date","market","market_cap_krw"}
    if not required.issubset(frame.columns):
        raise ValueError("Market and size data required for size neutralization")
    x = frame.copy()
    x["_rank"] = x.groupby(["date","market"]).market_cap_krw.rank(
        method="first", pct=True
    )
    x["size_bucket"] = np.minimum(
        np.floor(x["_rank"].mul(buckets)).fillna(-1).astype(int), buckets - 1
    )
    x.loc[x["_rank"].isna(), "size_bucket"] = -1
    return x.drop(columns="_rank")


def controlled_daily_ic(day: pd.DataFrame, factor: str, label: str) -> dict:
    """Correlate within-group rank residuals, not global ranks.

    Independent of the baseline raw IC; groups are (market, market-cap tercile).
    Requires >= MIN_STRATUM usable names per stratum and >= MIN_ELIGIBLE in total.
    The 2023 result was already explored, so significance is descriptive.
    """
    needed = ["market","size_bucket",factor,label]
    x = day[needed].dropna().copy()
    x = x.loc[x.size_bucket.ge(0)]
    if len(x) < MIN_ELIGIBLE:
        return {"ic_raw": np.nan,"ic_neutral":np.nan,"count":len(x),"groups":0}
    if x[factor].nunique() < 3 or x[label].nunique() < 3:
        return {"ic_raw":np.nan,"ic_neutral":np.nan,"count":len(x),"groups":0}
    raw = x[factor].rank().corr(x[label].rank())
    chunks = []
    for _, g in x.groupby(["market","size_bucket"], sort=True):
        if len(g) < MIN_STRATUM or g[factor].nunique() < 3 or g[label].nunique() < 3:
            continue
        # Independent ranks within each market-size bucket, centered at zero.
        a = (g[factor].rank(method="average", pct=True) - .5).to_numpy()
        b = (g[label].rank(method="average", pct=True) - .5).to_numpy()
        chunks.append((a,b))
    if not chunks:
        return {"ic_raw":float(raw),"ic_neutral":np.nan,"count":len(x),"groups":0}
    a = np.concatenate([v[0] for v in chunks])
    b = np.concatenate([v[1] for v in chunks])
    neutral = np.corrcoef(a,b)[0,1] if np.std(a)>0 and np.std(b)>0 else np.nan
    return {"ic_raw":float(raw),"ic_neutral":float(neutral),"count":len(x),
            "groups":len(chunks)}


def cohort_friction(day: pd.DataFrame, factor: str, label: str,
                    top_k: int, order_krw: int = 5_000_000,
                    max_turnover_participation: float = .005) -> dict:
    """Pick names on information at T; do not replace missing future labels.

    Capacity is evaluated against turnover observable by the T-close signal.
    Exit fills at T+H close are NOT guaranteed. No true executable orders.
    """
    if top_k < 1 or order_krw <= 0 or not 0 < max_turnover_participation <= 1:
        raise ValueError("Invalid cost/capacity assumptions")
    eligible = day.loc[day[factor].notna()].copy()
    if len(eligible) < top_k:
        return {"picked":0,"evaluable":0,"capacity_pass":0,"gross":np.nan,
                **{f"net_bps_{k}":np.nan for k in COST_SCENARIOS_BPS}}
    # FROZEN direction -1: choose lowest factor, ticker only for tie-breaks.
    picks = eligible.sort_values([factor,"ticker"], kind="stable").head(top_k)
    known_target = picks[label].dropna()
    # Intentional: picking requires NO future-label availability or next-day price.
    threshold = order_krw / max_turnover_participation
    capacity_ok = picks["turnover"].ge(threshold)
    # The "net" uses every selected name with a known outcome: it is NOT the
    # return of a self-financing portfolio nor a conditional replace-on-failure.
    gross = float(known_target.mean()) if len(known_target) else np.nan
    result = {
        "picked":int(len(picks)),
        "evaluable":int(len(known_target)),
        "unresolved":int(len(picks)-len(known_target)),
        "capacity_pass":int(capacity_ok.sum()),
        "gross":gross,
        "mean_signal_turnover_krw":float(picks.turnover.mean()),
    }
    for bps in COST_SCENARIOS_BPS:
        result[f"net_bps_{bps}"] = gross - bps / 10000 if np.isfinite(gross) else np.nan
    return result


def execute(data_dir: Path, output_dir: Path, modulus: int = 8) -> dict:
    """200-day warmup, fixed factor set, NO 2024-26 signal or label inspection."""
    if modulus < 1:
        raise ValueError("modulus must be positive")
    quality_file = data_dir/"market_structure_quality.json"
    q = json.loads(quality_file.read_text(encoding="utf-8"))
    if q.get("calendar",{}).get("reference_only_dates") or q.get("calendar",{}).get("observed_only_dates"):
        raise ValueError("Nonmatching calendar requires official investigation")
    private = data_dir/"_private"
    calendar = load_calendar(private/"krx_observed_sessions.csv",
                             _load_sample(private,modulus))
    if calendar.max().year != 2023:
        raise ValueError("2024-2026 holdouts must not be opened by v0.5")
    data = _load_sample(private,modulus)
    market = read_yearly_size_market_data(data_dir, (2019,2020,2021,2022,2023))
    # Only selected features, rather than a post-hoc search across all 188.
    pieces = []
    for ticker, group in data.groupby("ticker",sort=True):
        m = one_symbol_matrix(group,calendar,"2019-01-01","2023-12-31")
        if m.empty:
            continue
        ctx = group[["date","ticker","close","turnover","volume","unsafe_session"]]
        m = m.merge(ctx,on=["date","ticker"],validate="one_to_one")
        eligible = m.close.ge(1000) & m.turnover.ge(100_000_000) & m.volume.gt(0) & ~m.unsafe_session.fillna(True)
        cols=["date","ticker","turnover","forward_return_5","forward_return_10",*FROZEN_LOW_VOL_FACTORS]
        sub = m.loc[eligible,cols]
        if len(sub):
            pieces.append(sub)
    if not pieces:
        raise ValueError("No observable factor signals")
    signals = pd.concat(pieces,ignore_index=True)
    signals = signals.merge(market,on=["date","ticker"],validate="one_to_one",how="left")
    missing_meta = int(signals.market_cap_krw.isna().sum())
    signals = signals.loc[signals.market_cap_krw.gt(0) & signals.market.notna()].copy()
    signals = assign_size_buckets(signals)
    embargo = pd.DatetimeIndex(calendar[calendar.year<=2022][-10:]).union(
        pd.DatetimeIndex(calendar[calendar.year==2023][-10:]))
    signals = signals.loc[~signals.date.isin(embargo)]
    rows = []
    for date,day in signals.groupby("date",sort=True):
        for horizon in HORIZONS:
            target=f"forward_return_{horizon}"
            for feat in FROZEN_LOW_VOL_FACTORS:
                metric = controlled_daily_ic(day,feat,target)
                for k in TOP_K:
                    cost = cohort_friction(day,feat,target,k)
                    rows.append({"date":str(date.date()),"year":date.year,
                                 "feature":feat,"horizon":horizon,"top_k":k,
                                 **metric,**cost})
    daily = pd.DataFrame(rows)
    output_rows = []
    for (year,feat,horizon,k),g in daily.groupby(["year","feature","horizon","top_k"]):
        output_rows.append({
            "year":int(year),"split":"train" if year in TRAIN_YEARS else "2023_reused_exploratory",
            "factor":feat,"horizon":int(horizon),"top_k":int(k),
            "signal_days":int(len(g)),
            "raw_rank_ic":float(g.ic_raw.mean()),"market_size_neutral_rank_ic":float(g.ic_neutral.mean()),
            "days_with_neutral_groups":int(g.ic_neutral.notna().sum()),
            "mean_cross_section":float(g["count"].mean()),
            "mean_selected_gross":float(g.gross.mean()),
            "unresolved_future_label_fraction":float(g.unresolved.sum()/g.picked.sum()) if g.picked.sum() else None,
            "signal_turnover_capacity_pass_fraction":float(g.capacity_pass.sum()/g.picked.sum()) if g.picked.sum() else None,
            **{f"mean_after_{bps}bps":float(g[f"net_bps_{bps}"].mean()) for bps in COST_SCENARIOS_BPS},
        })
    agg = pd.DataFrame(output_rows).sort_values(["horizon","factor","top_k","year"])
    output_dir.mkdir(parents=True,exist_ok=True)
    agg.to_csv(output_dir/"v05_market_size_cost_aggregates.csv",index=False)
    report = {
        "status":"EXPLORATORY_NON_EXECUTABLE_MARKET_SIZE_AND_FRICTION_DIAGNOSTICS",
        "generated_utc":datetime.now(timezone.utc).isoformat(),
        "signal_stock_days":len(signals),"stock_codes":int(signals.ticker.nunique()),
        "meta_missing_excluded":missing_meta,
        "factor_names":FROZEN_LOW_VOL_FACTORS,
        "daily_diagnostic_rows":len(daily),
        "market_size_groups":"market × within-market date tercile; at least 8 observations per stratum",
        "cost_bps_scenarios":COST_SCENARIOS_BPS,
        "order_krw":5_000_000,
        "max_fraction_of_PREVIOUS_SIGNAL_DAY_turnover":.005,
        "holdout_2026_touched":False,
        "industry_neutralization":"NOT DONE — requires historical sector classifications",
        "pit_marketcap_caveat":"Marcap at signal close T, not independently verified against official point-in-time issuer master",
        "risk_and_execution_warnings":[
            "No order booking/capital/cash ledger. Trading PnL and actual fill prices not simulated.",
            "Gross future labels T+1 open -> T+H close may not represent executable closing auction prices.",
            "Roundtrip cost stress is hypothetical, not an official fee, tax or spread schedule.",
            "Missing target labels left unresolved, never replaced with hindsight-selected candidates.",
            "Ticker-code hash sample, not full stock market; historical delisting and split adjustments uncertified.",
            "2023 already viewed, NOT an independent out-of-sample test.",
            "Neutralized rank IC does not mean a market/size-neutral investable portfolio.",
        ]
    }
    (output_dir/"v05_summary.json").write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps({
        "status":report["status"],"stock_codes":report["stock_codes"],
        "signal_stock_days":report["signal_stock_days"],
        "aggregate_rows":len(agg),
        "example_2023_10d_k10":agg.loc[
            agg.year.eq(2023)&agg.horizon.eq(10)&agg.top_k.eq(10),
            ["factor","raw_rank_ic","market_size_neutral_rank_ic","mean_selected_gross","mean_after_100bps","signal_turnover_capacity_pass_fraction"]
        ].round(5).to_dict("records"),
    },ensure_ascii=False),flush=True)
    return report


def main():
    p=argparse.ArgumentParser(description="v0.5 size/market and execution stress; 2026 locked")
    p.add_argument("--data",required=True,type=Path)
    p.add_argument("--output",required=True,type=Path)
    p.add_argument("--modulus",default=8,type=int)
    args=p.parse_args()
    execute(args.data,args.output,args.modulus)


if __name__=="__main__":
    main()
