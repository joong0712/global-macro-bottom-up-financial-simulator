"""Point-in-time joins for DART, participant flows, and macro data.

Require the real public availability timestamp, not the fiscal period end.
No inputs are fetched, guessed or substituted from OHLCV.
"""
from __future__ import annotations
import re
import pandas as pd


def point_in_time_join(signals: pd.DataFrame, events: pd.DataFrame,
                       fields: tuple[str, ...], *, key: str = "ticker",
                       cutoff_kst: str = "15:30") -> pd.DataFrame:
    if not fields or len(set(fields)) != len(fields):
        raise ValueError("nonempty unique fields required")
    if not {"date", key}.issubset(signals.columns):
        raise ValueError("signals need date and key")
    if not {key, "available_at", *fields}.issubset(events.columns):
        raise ValueError("events need key, available_at and requested fields")
    if any(x in ("date", key, "available_at") for x in fields):
        raise ValueError("reserved requested field")
    if not re.fullmatch(r"(?:[01]\d|2[0-3]):[0-5]\d", cutoff_kst):
        raise ValueError("invalid Korean market cutoff")
    s, e = signals.copy(), events[[key, "available_at", *fields]].copy()
    if s[["date", key]].isna().any().any() or e[[key, "available_at"]].isna().any().any():
        raise ValueError("missing date, key or availability")
    if s.duplicated(["date", key]).any():
        raise ValueError("duplicate signal date/key")
    # UTC offset or Z is mandatory. Naive timestamps can cause future leaks.
    if not all(isinstance(x, str) and re.search(r"(?:Z|[+-]\d\d:\d\d)$", x)
               for x in e["available_at"]):
        raise ValueError("timezone-aware ISO available_at required")
    e["_public_utc"] = pd.to_datetime(e["available_at"], utc=True, errors="raise")
    if e.duplicated([key, "_public_utc"]).any():
        raise ValueError("ambiguous releases with identical publication time")
    s["_order"] = range(len(s))
    s["date"] = pd.to_datetime(s["date"], errors="raise").dt.normalize()
    s["_signal_utc"] = (
        s["date"].dt.tz_localize("Asia/Seoul") +
        pd.Timedelta(hours=int(cutoff_kst[:2]), minutes=int(cutoff_kst[3:]))
    ).dt.tz_convert("UTC")
    s, e = s.sort_values(["_signal_utc", key]), e.sort_values(["_public_utc", key])
    result = pd.merge_asof(
        s, e.drop(columns="available_at"), left_on="_signal_utc",
        right_on="_public_utc", by=key, direction="backward",
    ).sort_values("_order")
    if (result["_public_utc"].notna() & (result["_public_utc"] > result["_signal_utc"])).any():
        raise AssertionError("future data leaked into signal")
    return result[list(signals.columns) + list(fields) + ["_public_utc"]].rename(
        columns={"_public_utc": "data_available_at_utc"}
    ).reset_index(drop=True)


def join_dart_fundamentals(signals, filings, fields):
    return point_in_time_join(signals, filings, tuple(fields), key="ticker")


def join_investor_flows(signals, flows, fields):
    return point_in_time_join(signals, flows, tuple(fields), key="ticker")


def join_macro_releases(signals, macro, fields):
    return point_in_time_join(signals, macro, tuple(fields), key="series_id")
