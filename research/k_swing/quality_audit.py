"""Conservative diagnostics: candidates are NOT confirmed corporate actions/delistings."""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
import numpy as np
import pandas as pd


def xkrx_sessions(start, end) -> pd.DatetimeIndex:
    import exchange_calendars
    cal = exchange_calendars.get_calendar("XKRX", start=start, end=end)
    return pd.DatetimeIndex(cal.sessions_in_range(cal.first_session, cal.last_session)).tz_localize(None)


# Public KRX announcements (reported 2026-05-20) for ad-hoc closures not
# represented in some XKRX holiday-library releases. This is an explicit,
# auditable *explanation*, not a silent rewrite of the exchange calendar.
KNOWN_2026_KRX_CLOSURES = {
    "2026-06-03": "2026 local-election-day closure",
    "2026-07-17": "2026 Constitution Day closure",
}
KRX_CLOSURE_SOURCE = "https://www.yna.co.kr/amp/view/AKR20260520064200008"


def compare_calendars(observed, reference) -> dict:
    observed = pd.DatetimeIndex(observed).normalize().unique().sort_values()
    reference = pd.DatetimeIndex(reference).normalize().unique().sort_values()
    reference_only = [str(x.date()) for x in reference.difference(observed)]
    explained = [x for x in reference_only if x in KNOWN_2026_KRX_CLOSURES]
    unexplained = [x for x in reference_only if x not in KNOWN_2026_KRX_CLOSURES]
    return {
        "reference": "XKRX in exchange_calendars (independent, non-official)",
        "observed_sessions": int(len(observed)),
        "xkrx_sessions": int(len(reference)),
        "reference_only_dates": reference_only,
        "reference_only_explained_by_reported_krx_closures": explained,
        "reference_only_still_unexplained": unexplained,
        "closure_announcement_source": KRX_CLOSURE_SOURCE,
        "observed_only_dates": [str(x.date()) for x in observed.difference(reference)],
        "matches": observed.equals(reference),
        "warning": "Mismatch could represent source missing sessions OR XKRX not reflecting an ad-hoc holiday. Confirm with KRX.",
    }


def marcap_metadata(raw: pd.DataFrame, year: int) -> pd.DataFrame:
    if "Date" not in raw and raw.index.name == "Date":
        raw = raw.reset_index()
    needed = {"Date", "Code", "Name", "Stocks", "Market"}
    if not needed.issubset(raw.columns):
        raise ValueError("missing metadata: " + str(sorted(needed - set(raw.columns))))
    x = raw[["Date", "Code", "Name", "Stocks", "Market"]].copy()
    x["date"] = pd.to_datetime(x["Date"], errors="coerce").dt.normalize()
    market = x["Market"].astype("string").str.strip().replace({
        "코스피": "KOSPI", "코스닥": "KOSDAQ", "유가증권": "KOSPI",
    })
    x = x.loc[market.isin(["KOSPI", "KOSDAQ"]) & x.date.dt.year.eq(year)].copy()
    x["market"] = market.loc[x.index]
    x["ticker"] = x["Code"].astype("string").str.strip()
    x = x.loc[x.ticker.str.fullmatch(r"\d{1,6}").fillna(False)].copy()
    x["ticker"] = x.ticker.str.zfill(6)
    x["security_name"] = x["Name"].astype("string").str.strip()
    x["shares"] = pd.to_numeric(x["Stocks"], errors="coerce")
    x = x[["date", "ticker", "security_name", "shares", "market"]].copy()
    if x.duplicated(["date", "ticker"]).any():
        raise ValueError("duplicate metadata key")
    return x


def screen_year(prices: pd.DataFrame, metadata: pd.DataFrame,
                calendar: pd.DatetimeIndex, prev_state: pd.DataFrame | None = None):
    """Return (screened_prices, last_observation_by_ticker, aggregate_counts)."""
    x = prices.merge(metadata, on=["date", "ticker"], how="left", validate="one_to_one")
    if x.security_name.isna().all():
        raise ValueError("metadata join failed")
    x["_prev"] = False
    if prev_state is not None and not prev_state.empty:
        p = prev_state.copy()
        for col in ("open", "high", "low", "volume", "turnover"):
            p[col] = np.nan
        p["_prev"] = True
        x = pd.concat([p, x], ignore_index=True)
    x = x.sort_values(["ticker", "date"], kind="stable").reset_index(drop=True)
    grouped = x.groupby("ticker", sort=False)
    prev_date = grouped["date"].shift(1)
    prev_close = grouped["close"].shift(1)
    prev_shares = grouped["shares"].shift(1)
    prev_name = grouped["security_name"].shift(1)
    prev_market = grouped["market"].shift(1)
    sessions = pd.DatetimeIndex(calendar).normalize()
    if sessions.has_duplicates:
        raise ValueError("duplicate session dates")
    rank = pd.Series(range(len(sessions)), index=sessions)
    now_i, prev_i = x.date.map(rank), prev_date.map(rank)
    if now_i.isna().any():
        raise ValueError("source date absent from observed calendar")
    adjacent = (now_i - prev_i).eq(1)
    gap = (now_i - prev_i).gt(1)
    price_jump = adjacent & x.close.div(prev_close.where(prev_close.gt(0))).sub(1).abs().gt(.35)
    share_ratio = x.shares.div(prev_shares.where(prev_shares.gt(0)))
    shares_shift = adjacent & (share_ratio.gt(1.25) | share_ratio.lt(.8))
    rename = (prev_name.notna() & x.security_name.notna() & x.security_name.ne(prev_name)).fillna(False)
    transfer = (prev_market.notna() & x.market.notna() & x.market.ne(prev_market)).fillna(False)
    unsafe = (price_jump | shares_shift | rename | transfer).fillna(False)
    current = x.loc[~x["_prev"]].copy()
    current["unsafe_session"] = unsafe.loc[current.index].astype(bool)
    summary = {
        "suspected_price_discontinuities": int(price_jump.loc[current.index].sum()),
        "suspected_share_count_changes": int(shares_shift.loc[current.index].sum()),
        "security_name_changes": int(rename.loc[current.index].sum()),
        "market_transfers": int(transfer.loc[current.index].sum()),
        "observation_gaps": int(gap.loc[current.index].sum()),
        "quarantined_rows": int(current.unsafe_session.sum()),
        "missing_security_names": int(current.security_name.isna().sum()),
    }
    tail = current.groupby("ticker", sort=False).tail(1)[
        ["date", "ticker", "close", "shares", "security_name", "market"]].copy()
    # Preserve tickers absent in this year, or old delistings disappear from
    # inactive/universe analysis and later reappearances lose identity history.
    if prev_state is not None and not prev_state.empty:
        tail = (pd.concat([prev_state, tail], ignore_index=True)
                .sort_values(["ticker", "date"], kind="stable")
                .groupby("ticker", sort=False).tail(1).reset_index(drop=True))
    screened = current[["date", "ticker", "open", "high", "low", "close", "volume", "turnover", "unsafe_session"]]
    return screened.sort_values(["date", "ticker"]), tail, summary


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", type=Path, required=True)
    parser.add_argument("--start-year", type=int, default=2017)
    parser.add_argument("--end-year", type=int, default=2026)
    a = parser.parse_args(argv)
    private = a.data / "_private"
    cal = pd.read_csv(private / "krx_observed_sessions.csv")
    dates = pd.DatetimeIndex(pd.to_datetime(cal["date"]).dt.normalize())
    if len(dates) < 5:
        raise ValueError("not enough market sessions")
    xkrx = xkrx_sessions(dates.min(), dates.max())
    cal_qa = compare_calendars(dates, xkrx)
    previous, counts = None, []
    for year in range(a.start_year, a.end_year + 1):
        raw = a.data / "_raw" / f"marcap-{year}.parquet"
        if not raw.is_file():
            raise FileNotFoundError("rerun marcap_ingest with --keep-raw; no upstream re-download here")
        prices = pd.read_csv(private / f"kswing_prices_{year}.csv.gz", parse_dates=["date"], dtype={"ticker": "string"})
        metadata = marcap_metadata(pd.read_parquet(raw), year)
        safe, previous, summary = screen_year(prices, metadata, dates, previous)
        safe.to_csv(private / f"kswing_screened_{year}.csv.gz", index=False, compression="gzip", date_format="%Y-%m-%d")
        summary["year"] = year
        counts.append(summary)
        print(json.dumps(summary, ensure_ascii=False), flush=True)
    rank = pd.Series(range(len(dates)), index=dates)
    inactive = int((previous.date.map(rank) < len(dates) - 20).sum())
    report = {
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "calendar": cal_qa,
        "yearly_screening": counts,
        "potentially_inactive_ticker_codes_not_seen_in_last_20_source_sessions": inactive,
        "certified_for_backtesting": False,
        "critical_notes": [
            "Name, share count, market changes and price jumps are CANDIDATES; not verified splits or delistings.",
            "Corporate actions, identifiers, common-stock listing masters and official KRX calendar need independent confirmation.",
            "Screened CSV includes unsafe_session. Raw/normalized data remain private.",
        ],
    }
    dest = a.data / "market_structure_quality.json"
    dest.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"result": "AUDIT_COMPLETE_NOT_CERTIFIED", "calendar_matches": cal_qa["matches"]}), flush=True)


if __name__ == "__main__":
    main()
