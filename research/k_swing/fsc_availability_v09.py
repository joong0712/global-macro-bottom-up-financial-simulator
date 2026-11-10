"""v0.9 time-of-availability audit for FSC dated issuer snapshots.

A date-labelled historical row fetched today is NOT proof it was available
at that date. Require independently observed, time-zoned publication AND
historical-vintage timestamps. This function never constructs missing metadata.
"""
from __future__ import annotations
import re
import pandas as pd


def fsc_snapshot_signal_gate(
    stock_signals: pd.DataFrame, 
    official_reference: pd.DataFrame,
    calendar: pd.DatetimeIndex,
    *,
    cutoff_kst: str="15:30",
) -> tuple[pd.DataFrame,dict]:
    """Left join on exact date/short ticker; return availability evidence status.

    This is a coverage AUDIT only, not a tradable factor.
    - basDt is data as-of date, not publication or vintage.
    - first_public_at: independently verified timestamp, timezone-aware.
    - historical_vintage_observed_at: earliest observation of precise historical
      value, not retrieval of a revised backfilled history today.
    - Source's next business-day 13:00 update is earliest plausible schedule;
      later actual publication / vintage wins. KRX sessions used conservatively.
    """
    needed={"basDt","srtnCd","isinCd","first_public_at","historical_vintage_observed_at"}
    if not {"date","ticker"}.issubset(stock_signals) or not needed.issubset(official_reference):
        raise ValueError("signals and official timestamped reference fields required")
    if not re.fullmatch(r"(?:[01]\d|2[0-3]):[0-5]\d",cutoff_kst):
        raise ValueError("invalid signal cutoff")
    s=stock_signals.copy()
    s["date"]=pd.to_datetime(s.date,errors="raise").dt.normalize()
    s["ticker"]=s.ticker.astype("string").str.zfill(6)
    if s.duplicated(["date","ticker"]).any():
        raise ValueError("duplicate signal-day identity")
    if s.date.dt.year.max()>2023:
        raise ValueError("holdout year 2024-2026 is locked")
    cal=pd.DatetimeIndex(calendar).normalize().sort_values()
    if cal.has_duplicates or len(cal)<2:
        raise ValueError("exact unique historical session calendar required")
    e=official_reference[list(needed)].copy()
    e["date"]=pd.to_datetime(e.basDt.astype("string"),format="%Y%m%d",errors="raise").dt.normalize()
    e["ticker"]=e.srtnCd.astype("string").str.zfill(6)
    if e.date.dt.year.max()>2023:
        raise ValueError("2024-2026 reference time period locked")
    if not e.isinCd.astype("string").str.fullmatch(r"KR[A-Z0-9]{10}").all():
        raise ValueError("invalid official Korean ISIN")
    if e.duplicated(["date","ticker"]).any():
        raise ValueError("ambiguous official reference for same date and ticker")
    for name in ("first_public_at","historical_vintage_observed_at"):
        if not e[name].map(lambda z:isinstance(z,str) and bool(re.search(r"(?:Z|[+-]\d\d:\d\d)$",z))).all():
            raise ValueError(f"{name} must be genuine timezone-aware ISO timestamp")
        e[name+"_utc"]=pd.to_datetime(e[name],utc=True,format="mixed",errors="raise")
    # An official snapshot for T might not be obtainable until T+1 >13:00
    # exchange time. This is conservative; does NOT prove actual T+1 availability.
    next_idx=cal.searchsorted(e.date.values,side="right")
    next_date=cal.take(next_idx.clip(max=len(cal)-1))
    e["_scheduled_utc"]=(next_date.tz_localize("Asia/Seoul")+
                           pd.Timedelta(hours=13)).tz_convert("UTC")
    e.loc[next_idx>=len(cal),"_scheduled_utc"]=pd.NaT
    close_hour,close_min=map(int,cutoff_kst.split(":"))
    s["_signal_utc"]=(s.date.dt.tz_localize("Asia/Seoul")+
                      pd.Timedelta(hours=close_hour,minutes=close_min)).dt.tz_convert("UTC")
    matched=s.merge(
        e[["date","ticker","isinCd","first_public_at_utc",
           "historical_vintage_observed_at_utc","_scheduled_utc"]],
        on=["date","ticker"],how="left",validate="one_to_one")
    valid=(
        matched["isinCd"].notna()&
        matched["_scheduled_utc"].notna()&
        matched["first_public_at_utc"].le(matched["_signal_utc"])&
        matched["historical_vintage_observed_at_utc"].le(matched["_signal_utc"])&
        matched["_scheduled_utc"].le(matched["_signal_utc"])
    )
    # An exact same-day T reference can never pass T close if its published
    # update schedule is T+1. Do NOT repurpose T data as if available at T.
    matched["signal_time_reference_verified_available"]=valid.fillna(False)
    stats={
        "status":"COVERAGE_AUDIT_ONLY_NOT_A_CORPORATE_ACTION_CERTIFICATION",
        "signal_days":len(matched),
        "exact_day_reference_matches":int(matched.isinCd.notna().sum()),
        "historical_reference_admissible_at_signal_T":int(valid.sum()),
        "reference_dates_not_usable_as_same_date_signals":int((~valid).sum()),
        "earliest_scheduled_release":"Next observed exchange session at 13:00 KST, not a guarantee",
        "requires_real_first_publication_and_historical_vintage":True,
        "official_split_and_delisting_full_history_verified":False,
        "2026_holdout_opened":False,
    }
    return matched[["date","ticker","isinCd",
                    "signal_time_reference_verified_available"]].copy(),stats
