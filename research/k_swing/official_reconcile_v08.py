"""v0.8 official reference reconciliation: fail closed on missing ISIN/date history.

Authorized FSC as-of daily snapshots are inputs, not proof of complete listing,
delisting, split-adjusted returns or an investable common-share universe.
Never fill historical classifications with today's issuer reference.
"""
from __future__ import annotations
from pathlib import Path
import pandas as pd
import numpy as np

REQUIRED_PRICES={"date","ticker","close"}
REQUIRED_FSC={"basDt","isinCd","srtnCd"}
REQUIRED_EVENTS={"security_id","event_type","effective_date","first_public_at",
                 "official_source","official_url","source_record_id","ticker"}


def reconcile_official_snapshots(
    stock_days: pd.DataFrame,
    fsc_snapshots: pd.DataFrame | None,
    events: pd.DataFrame | None = None,
) -> tuple[pd.DataFrame,dict]:
    """Exact day+symbol joins; no asof fill or implied splits/delistings."""
    if not REQUIRED_PRICES.issubset(stock_days):
        raise ValueError("missing stock-day price/date/ticker fields")
    price=stock_days[["date","ticker","close"]].copy()
    price["date"]=pd.to_datetime(price.date,errors="raise").dt.normalize()
    price["ticker"]=price.ticker.astype("string").str.zfill(6)
    if price.date.dt.year.max()>=2024:
        raise ValueError("2024-2026 research return holdouts remain locked")
    if price.duplicated(["date","ticker"]).any():
        raise ValueError("duplicate ticker/date in market prices")
    if price.date.isna().any() or price.ticker.isna().any():
        raise ValueError("missing market date or ticker")
    dates=price.date.nunique()
    refs=None
    if fsc_snapshots is not None and not fsc_snapshots.empty:
        if not REQUIRED_FSC.issubset(fsc_snapshots):
            raise ValueError("official FSC snapshots require basDt, isinCd, srtnCd")
        refs=fsc_snapshots.loc[:,["basDt","isinCd","srtnCd"]].copy()
        refs["date"]=pd.to_datetime(refs.basDt.astype("string"),format="%Y%m%d",errors="raise")
        refs["ticker"]=refs.srtnCd.astype("string").str.zfill(6)
        refs["security_id"]=refs.isinCd.astype("string")
        if not refs.security_id.str.fullmatch(r"KR[A-Z0-9]{10}").all():
            raise ValueError("invalid historical ISIN; never trust ticker-only universe")
        if refs.duplicated(["date","ticker"]).any():
            raise ValueError("one ticker maps to multiple official ISINs on same date")
        if refs.duplicated(["date","security_id"]).any():
            raise ValueError("one official ISIN maps to multiple tickers on same date")
        if refs.date.dt.year.max()>=2024:
            raise ValueError("holdout reference date locked as well")
        refs=refs[["date","ticker","security_id"]]
        combined=price.merge(refs,on=["date","ticker"],how="left",validate="one_to_one",
                             indicator=True)
        combined["status"]=np.where(combined._merge.eq("both"),
                                    "EXACT_OFFICIAL_SNAPSHOT_MATCH","NO_SAME_DAY_OFFICIAL_RECORD")
        combined=combined.drop(columns="_merge")
    else:
        combined=price.assign(security_id=pd.NA,status="NO_AUTHORIZED_OFFICIAL_SNAPSHOTS")
    matched=int(combined.security_id.notna().sum())
    reused=0
    if refs is not None:
        reused=int(refs.groupby("ticker").security_id.nunique().gt(1).sum())
    event_rows=0
    if events is not None and not events.empty:
        from .official_events_v07 import validate_event_records
        vetted=validate_event_records(events)
        event_rows=len(vetted)
        # The event ledger still must undergo source-completeness verification.
        # Passing the schema never automatically certifies adjusted OHLCV.
    out={
        "status":"OFFICIAL_COVERAGE_INCOMPLETE_OR_UNCERTIFIED",
        "stock_days":len(price),"unique_signal_dates":int(dates),
        "same_day_verified_isin_matches":matched,
        "missing_exact_day_isin_matches":int(len(price)-matched),
        "exact_date_match_fraction":matched/len(price) if len(price) else 0,
        "ticker_codes_with_multiple_official_isins_across_dates":reused,
        "schema_valid_event_rows":event_rows,
        "all_dates_have_reference_snapshots":bool(refs is not None and
                    set(price.date).issubset(set(refs.date))),
        "delisting_outcomes_verified":False,
        "full_historical_ordinary_share_universe_verified":False,
        "price_adjustments_verified":False,
        "point_in_time_industry_history_verified":False,
        "2026_holdout_opened":False,
        "blocking_reasons":[
            "One or many authorized as-of snapshots do not independently prove that delisted and disappeared securities are captured.",
            "Daily issuer reference alone cannot correct splits, mergers, stock dividends or final delisting payouts.",
            "Official event provenance and exact legal redistribution rights require separate certification.",
            "Never substitute current ticker->ISIN metadata for historical trading sessions.",
        ],
    }
    if reused:
        out["blocking_reasons"].append(
            "Ticker reused across distinct historical security ISINs: must split security identities")
    return combined,out


def read_private_snapshots(paths: list[Path]) -> pd.DataFrame:
    if not paths:
        raise ValueError("official history files are absent")
    frames=[]
    for p in paths:
        if not p.is_file():
            raise FileNotFoundError(p)
        x=pd.read_csv(p,dtype={"basDt":"string","srtnCd":"string","isinCd":"string"})
        frames.append(x)
    return pd.concat(frames,ignore_index=True)
