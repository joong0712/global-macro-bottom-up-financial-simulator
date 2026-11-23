"""Predeclared upside/downside and incremental-factor diagnostics; not a trading backtest."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import numpy as np
import pandas as pd
from .factor_matrix_v04 import one_symbol_matrix
from .factor_pilot_v04 import is_sampled

VOL = "ta__parkinson_vol_20"
SECONDARY = ("ta__stoch_rsi_14", "ta__macd_hist_pct", "ta__ichi_cloud_top_gap")
PERIODS = {"2019_20": (2019, 2020), "2021_22": (2021, 2022)}
COST_BPS = 50
MIN_N = 30

def analyze(panel: pd.DataFrame) -> pd.DataFrame:
    z = panel.copy()
    required = {"date", "ticker", VOL, *SECONDARY, "forward_return_5", "forward_return_10"}
    if not required.issubset(z):
        raise ValueError("missing fixed factor/label columns")
    z["date"] = pd.to_datetime(z.date)
    if z.date.isna().any() or not z.date.dt.year.isin((2019, 2020, 2021, 2022)).all():
        raise ValueError("holdout locked: only 2019-22")
    if z.duplicated(["date", "ticker"]).any():
        raise ValueError("duplicate stock/date")
    if "unsafe_session" in z and z.unsafe_session.fillna(True).astype(bool).any():
        raise ValueError("unsafe observations")
    for f in (VOL, *SECONDARY):
        z[f] = pd.to_numeric(z[f], errors="coerce").replace([np.inf, -np.inf], np.nan)
        z["rank__"+f] = z.groupby("date")[f].rank(pct=True)
    z["vol_high"] = z["rank__"+VOL] > .8
    rows = []
    for period, years in PERIODS.items():
        p = z.loc[z.date.dt.year.isin(years)]
        for horizon in (5, 10):
            r = pd.to_numeric(p[f"forward_return_{horizon}"], errors="coerce")
            eligible = r.notna() & p[VOL].notna()
            vol = eligible & p.vol_high
            cohorts = {"universe": eligible, "high_vol": vol}
            for f in SECONDARY:
                cohorts["high_vol_plus_"+f] = vol & p["rank__"+f].gt(.8)
                cohorts["high_vol_not_high_"+f] = vol & p["rank__"+f].le(.8) & p[f].notna()
            for name, mask in cohorts.items():
                sample = r.loc[mask]
                n = len(sample)
                rows.append({
                    "period": period, "horizon": horizon, "cohort": name, "observations": n,
                    "up_3_pct": float(sample.ge(.03).mean()) if n >= MIN_N else np.nan,
                    "up_5_pct": float(sample.ge(.05).mean()) if n >= MIN_N else np.nan,
                    "down_3_pct": float(sample.le(-.03).mean()) if n >= MIN_N else np.nan,
                    "down_5_pct": float(sample.le(-.05).mean()) if n >= MIN_N else np.nan,
                    "mean_gross_pct": float(100*sample.mean()) if n >= MIN_N else np.nan,
                    "median_gross_pct": float(100*sample.median()) if n >= MIN_N else np.nan,
                    "mean_net_50bps_pct": float(100*sample.mean() - COST_BPS/100) if n >= MIN_N else np.nan,
                    "p05_gross_pct": float(100*sample.quantile(.05)) if n >= MIN_N else np.nan,
                    "independent_confirmation": False,
                    "realized_portfolio_return": False,
                })
    return pd.DataFrame(rows)

def incremental(result: pd.DataFrame) -> pd.DataFrame:
    a = result.loc[result.cohort.eq("high_vol")].set_index(["period", "horizon"])
    out = []
    for f in SECONDARY:
        b = result.loc[result.cohort.eq("high_vol_plus_"+f)].set_index(["period", "horizon"])
        for idx in a.index.intersection(b.index):
            base, joint = a.loc[idx], b.loc[idx]
            out.append({"period": idx[0], "horizon": idx[1], "second_factor": f,
                        "high_vol_n": int(base.observations), "joint_n": int(joint.observations),
                        **{f"joint_minus_highvol_{metric}_pp": 100*(joint[metric]-base[metric])
                           for metric in ("up_3_pct","up_5_pct","down_3_pct","down_5_pct")},
                        "joint_minus_highvol_mean_net_pct_points":
                            joint.mean_net_50bps_pct-base.mean_net_50bps_pct,
                        "incremental_information_causal": False})
    return pd.DataFrame(out)

def load_private(root: Path, modulus: int) -> pd.DataFrame:
    if modulus < 1:
        raise ValueError("invalid modulus")
    private = root / "_private"
    pieces = []
    for year in range(2017, 2023):
        file = private / f"kswing_screened_{year}.csv.gz"
        if not file.is_file():
            raise FileNotFoundError(str(file))
        for part in pd.read_csv(file, parse_dates=["date"], dtype={"ticker": "string"}, chunksize=100_000):
            part = part.loc[part.ticker.map(lambda t: is_sampled(t, modulus))]
            if not part.empty:
                pieces.append(part)
    if not pieces:
        raise ValueError("empty data")
    prices = pd.concat(pieces, ignore_index=True)
    calendar = pd.DatetimeIndex(pd.to_datetime(pd.read_csv(private / "krx_observed_sessions.csv").date))
    panel = pd.concat([one_symbol_matrix(bars, calendar, "2019-01-01", "2022-12-31")
                       for _, bars in prices.groupby("ticker", sort=True)], ignore_index=True)
    return panel

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", type=Path, required=True)
    ap.add_argument("--aggregate-output", type=Path, required=True)
    ap.add_argument("--modulus", type=int, default=16)
    args = ap.parse_args()
    panel = load_private(args.data, args.modulus)
    result = analyze(panel)
    delta = incremental(result)
    args.aggregate_output.mkdir(parents=True, exist_ok=True)
    result.to_csv(args.aggregate_output/"risk_reward_aggregate.csv", index=False)
    delta.to_csv(args.aggregate_output/"incremental_aggregate.csv", index=False)
    manifest = {"status":"EXPLORATORY_RISK_REWARD_NOT_VALIDATED_ALPHA",
                "panel_rows":len(panel),"risk_reward_rows":len(result),"incremental_rows":len(delta),
                "roundtrip_cost_bps_assumption":COST_BPS,
                "not_officially_adjusted":True,"independent_validation":False,
                "overlapping_labels":True,"no_portfolio_construction":True,
                "holdout_2026_touched":False,"live_trading_allowed":False}
    (args.aggregate_output/"manifest.json").write_text(json.dumps(manifest,indent=2))
    print(json.dumps(manifest))

if __name__ == "__main__":
    main()
