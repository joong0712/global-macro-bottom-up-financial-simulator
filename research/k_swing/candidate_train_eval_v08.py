"""Run 12 pre-specified candidate expressions on 2019-22 TRAINING ONLY.

No 2023 reused validation, no 2024-26 untouched confirmation.
Candidate orientation uses discovery 2019-20, then 2021-22 is descriptive
internal verification, NOT a new untouched out-of-sample evaluation.
"""
from __future__ import annotations
import argparse, json
from datetime import datetime,timezone
from pathlib import Path
import pandas as pd

from .data import validate_prices,load_calendar
from .factor_pilot_v04 import is_sampled
from .factor_matrix_v04 import one_symbol_matrix
from .candidate_research_v08 import candidate_expressions,evaluate_train_only,FEATURES


def train_data(private:Path,modulus:int=16) -> pd.DataFrame:
    if modulus<1:
        raise ValueError("invalid code-hash modulus")
    records=[]
    for year in range(2017,2023):
        path=private/f"kswing_screened_{year}.csv.gz"
        if not path.is_file():
            raise FileNotFoundError(path)
        for part in pd.read_csv(path,dtype={"ticker":"string"},
                                parse_dates=["date"],chunksize=100000):
            selected=part.ticker.map(lambda x:is_sampled(x,modulus))
            sub=part.loc[selected]
            if len(sub):records.append(sub)
    if not records:
        raise ValueError("empty training sample")
    return validate_prices(pd.concat(records,ignore_index=True))


def run(data_dir:Path,output:Path,modulus:int=16) -> dict:
    quality=json.loads((data_dir/"market_structure_quality.json").read_text())
    c=quality.get("calendar",{})
    if c.get("reference_only_dates") or c.get("observed_only_dates"):
        raise ValueError("calendar mismatch")
    frame=train_data(data_dir/"_private",modulus)
    dates=load_calendar(data_dir/"_private"/"krx_observed_sessions.csv",frame)
    if dates.max().year>2022:
        raise ValueError("2023 or later not allowed in new-formula selection")
    embargo=dates[dates.year==2022][-10:]
    pieces=[]
    for ticker,group in frame.groupby("ticker",sort=True):
        mat=one_symbol_matrix(group,dates,"2019-01-01","2022-12-31")
        if mat.empty:
            continue
        m=mat.merge(group[["date","ticker","close","turnover","volume","unsafe_session"]],
                    on=["date","ticker"],validate="one_to_one")
        eligible=m.close.ge(1000)&m.turnover.ge(100_000_000)&m.volume.gt(0)&~m.unsafe_session.fillna(True)
        part=m.loc[eligible & ~m.date.isin(embargo)].copy()
        if part.empty:
            continue
        expr=candidate_expressions(part)
        piece=pd.concat([
            part[["date","forward_return_5","forward_return_10"]].reset_index(drop=True),
            expr.reset_index(drop=True)
        ],axis=1)
        pieces.append(piece)
    if not pieces:
        raise ValueError("empty eligible training rows")
    panel=pd.concat(pieces,ignore_index=True)
    if panel.date.dt.year.max()>2022:
        raise AssertionError("future labels not allowed")
    results=[]
    for h in (5,10):
        annual,summary=evaluate_train_only(panel,horizon=h)
        annual["horizon"]=h
        summary["horizon"]=h
        results.append((annual,summary))
    yearly=pd.concat([x[0] for x in results],ignore_index=True)
    ranks=pd.concat([x[1] for x in results],ignore_index=True)
    output.mkdir(parents=True,exist_ok=True)
    yearly.to_csv(output/"v08_candidate_2019_22_annual_ic.csv",index=False)
    ranks.to_csv(output/"v08_candidate_discovery_internal_summary.csv",index=False)
    manifest={
        "status":"TRAINING_ONLY_CANDIDATE_GENERATION_NO_TRADE_CLAIM",
        "created_utc":datetime.now(timezone.utc).isoformat(),
        "ticker_hash_modulus":modulus,"ticker_days":int(len(panel)),
        "unique_training_dates":int(panel.date.nunique()),
        "candidate_expressions":len(FEATURES),"candidate_horizon_pairs":len(ranks),
        "positive_ic_both_internal_subperiods":int(ranks.positive_in_both_training_subperiods.sum()),
        "selection_direction_based_on":"2019-2020 only",
        "internal_check":"2021-2022 already explored in previous baseline research",
        "2023_2024_2025_2026_not_opened":True,
        "not_tradable_alpha":True,
        "no_official_corporate_action_price_adjustment":True,
        "warnings":[
            "Original indicators and candidate formulas strongly correlated; 24 candidates are NOT independent tests",
            "2019-22 data already studied previously, so internal split is NOT pristine OOS",
            "Rank IC says nothing about real trading tax/fees or fillable portfolio return",
            "Official historical split/delisting data still required before live strategy claims",
        ],
    }
    (output/"v08_candidate_research_manifest.json").write_text(
        json.dumps(manifest,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps({"status":manifest["status"],
                      "signals":manifest["ticker_days"],
                      "candidate_pairs":len(ranks),
                      "internal_positive":manifest["positive_ic_both_internal_subperiods"],
                      "2026_locked":True}),flush=True)
    return manifest


def main():
    p=argparse.ArgumentParser(description="candidate expression training 2019-22 ONLY")
    p.add_argument("--data",type=Path,required=True)
    p.add_argument("--output",type=Path,required=True)
    p.add_argument("--modulus",type=int,default=16)
    a=p.parse_args()
    run(a.data,a.output,a.modulus)


if __name__=="__main__":
    main()
