"""Private real OHLCV prototype execution stress, 2023 ALREADY INSPECTED.

This exercises *unadjusted* KRX-derived prints, not official filled trades,
verified tax schedules, clean corporate actions or an investable PnL record.
No symbol-level output is published. The 2026 confirmation set stays locked.
"""
from __future__ import annotations
import argparse
import json
from datetime import datetime,timezone
from pathlib import Path
import pandas as pd

from .data import load_calendar
from .factor_pilot_v04 import _load_sample
from .factor_matrix_v04 import one_symbol_matrix
from .execution_prototype_v07 import simulate

FROZEN_FACTORS=(
    "ta__atr_wilder_pct_7",
    "ta__parkinson_vol_20",
)
COST_BPS=(20,50,100,200)
TOPK=(3,10)
HORIZONS=(5,10)


def run(data_dir:Path,output_dir:Path,modulus:int=16) -> dict:
    if modulus<1:
        raise ValueError("invalid ticker-code sampling modulus")
    report=json.loads((data_dir/"market_structure_quality.json").read_text())
    if report.get("calendar",{}).get("reference_only_dates") or report.get("calendar",{}).get("observed_only_dates"):
        raise ValueError("unresolved KRX market calendar mismatch")
    sample=_load_sample(data_dir/"_private",modulus)
    sessions=load_calendar(data_dir/"_private"/"krx_observed_sessions.csv",sample)
    if sessions.max().year>2023:
        raise ValueError("holdouts 2024-2026 are locked")
    test_sessions=sessions[sessions.year==2023]
    scored=[]
    bars=[]
    for ticker,rows in sample.groupby("ticker",sort=True):
        mat=one_symbol_matrix(rows,sessions,"2023-01-01","2023-12-31")
        if mat.empty:
            continue
        actual=rows.loc[rows.date.dt.year.eq(2023)].copy()
        bars.append(actual[["date","ticker","open","close","unsafe_session"]])
        m=mat.merge(rows[["date","ticker","close","turnover","volume","unsafe_session"]],
                    on=["date","ticker"],validate="one_to_one")
        eligible=m.close.ge(1000)&m.turnover.ge(100_000_000)&m.volume.gt(0)&~m.unsafe_session.fillna(True)
        for factor in FROZEN_FACTORS:
            q=m.loc[eligible & m[factor].notna(),["date","ticker","turnover",factor]].copy()
            q=q.rename(columns={factor:"score"})
            q["factor"]=factor
            scored.append(q)
    if not bars or not scored:
        raise ValueError("no market input to run provisional ledger")
    all_bars=pd.concat(bars,ignore_index=True)
    all_signals=pd.concat(scored,ignore_index=True)
    outputs=[]
    for factor in FROZEN_FACTORS:
        signal=all_signals.loc[all_signals.factor.eq(factor),["date","ticker","turnover","score"]]
        for horizon in HORIZONS:
            for top_k in TOPK:
                for bps in COST_BPS:
                    _,out=simulate(
                        all_bars,signal,test_sessions,horizon=horizon,
                        top_k=top_k,initial_cash_krw=100_000_000,
                        ticket_krw=5_000_000,max_positions=10,
                        assumed_roundtrip_bps=float(bps),
                        max_signal_turnover_fraction=.005,
                    )
                    outputs.append({
                        "factor":factor,"horizon":horizon,"top_k":top_k,
                        "assumed_cost_bps":bps,
                        "scenario_status":out["status"],
                        "completed_trades":out["completed_trades"],
                        "reported_terminal_cash_krw":out["end_cash_only_if_all_resolved"],
                        "reported_hypothetical_return":out["net_return_only_if_all_resolved"],
                        "any_unresolved_exit":out["status"].startswith("BLOCKED"),
                        **{f"skipped_{k}":v for k,v in out["skipped_reason_counts"].items()}
                    })
    agg=pd.DataFrame(outputs)
    output_dir.mkdir(parents=True,exist_ok=True)
    agg.to_csv(output_dir/"v08_real_bar_provisional_execution_scenarios.csv",index=False)
    meta={
        "status":"PROVISIONAL_REAL_BAR_LEDGER_NOT_TRUE_EXECUTION_BACKTEST",
        "created_utc":datetime.now(timezone.utc).isoformat(),
        "source_stock_codes":int(sample.ticker.nunique()),
        "2023_signal_dates":int(all_signals.date.nunique()),
        "scenarios":len(agg),
        "scenarios_with_unresolved_fills_or_actions":int(agg.any_unresolved_exit.sum()),
        "official_stock_events_verified":False,
        "official_KRX_ISIN_history_verified":False,
        "broker_execution_verified":False,
        "period_specific_official_fees_and_taxes_verified":False,
        "2023_is_reused_exploratory":True,
        "2026_holdout_touched":False,
        "meaning":"Only a conservation-of-cash/position and assumed-cost engineering stress on historical unadjusted prints; NOT verified profitability.",
        "warning":"Do not select a profitable scenario after inspecting 2023 as a strategy.",
    }
    (output_dir/"v08_provisional_execution_manifest.json").write_text(
        json.dumps(meta,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps({"status":meta["status"],"scenarios":len(agg),
                      "blocked":meta["scenarios_with_unresolved_fills_or_actions"],
                      "2026_locked":True}),flush=True)
    return meta


def main():
    p=argparse.ArgumentParser(description="v0.8 2023 real bars / provisional cash ledger")
    p.add_argument("--data",required=True,type=Path)
    p.add_argument("--output",required=True,type=Path)
    p.add_argument("--modulus",type=int,default=16)
    args=p.parse_args()
    run(args.data,args.output,args.modulus)


if __name__=="__main__":
    main()
