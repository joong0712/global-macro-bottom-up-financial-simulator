"""Acquire yearly KRX-derived marcap Parquet privately, validate and normalize.

No market-data files are committed or uploaded. Usage is subject to source/exchange terms.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

import pandas as pd

SOURCE = "https://github.com/FinanceData/marcap"
DEFAULT_REF = "94c138df4bf7376be8d28f979edb14020e2a547a"
COLS = ("date", "ticker", "open", "high", "low", "close", "volume", "turnover")
REQUIRED = ("Date", "Code", "Open", "High", "Low", "Close", "Volume", "Amount", "Market")
MARKETS = {"KOSPI": "KOSPI", "KOSDAQ": "KOSDAQ", "코스피": "KOSPI", "코스닥": "KOSDAQ", "유가증권": "KOSPI"}


def url_for(year: int, ref: str = DEFAULT_REF) -> str:
    if year < 1995 or year > 2100:
        raise ValueError("invalid year")
    if not re.fullmatch(r"(?:[0-9a-f]{40}|master)", ref):
        raise ValueError("invalid git ref")
    return f"https://raw.githubusercontent.com/FinanceData/marcap/{ref}/data/marcap-{year}.parquet"


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as source:
        while chunk := source.read(1024 * 1024):
            h.update(chunk)
    return h.hexdigest()


def download(year: int, output: Path, ref: str = DEFAULT_REF) -> dict:
    url = url_for(year, ref)
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.is_file() and output.stat().st_size > 1000:
        return {"year": year, "sha256": sha256_file(output), "bytes": output.stat().st_size, "cached": True, "source_url": url}
    partial = output.with_suffix(".part")
    for retry in range(3):
        try:
            size = 0
            request = Request(url, headers={"User-Agent": "K-SWING-private-research/0.2"})
            with urlopen(request, timeout=90) as remote, partial.open("wb") as local:
                while chunk := remote.read(1024 * 1024):
                    size += len(chunk)
                    if size > 128 * 1024 * 1024:
                        raise ValueError("unexpected large source")
                    local.write(chunk)
            if size < 1000:
                raise ValueError("unexpected small source")
            partial.replace(output)
            return {"year": year, "sha256": sha256_file(output), "bytes": size, "cached": False, "source_url": url}
        except (HTTPError, URLError, OSError) as exc:
            partial.unlink(missing_ok=True)
            if retry == 2:
                raise RuntimeError(f"{year} download failed: {exc}") from exc
            time.sleep(2 ** retry)
        except Exception:
            partial.unlink(missing_ok=True)
            raise
    raise AssertionError("unreachable")


def normalize_marcap(frame: pd.DataFrame, year: int) -> tuple[pd.DataFrame, dict]:
    if "Date" not in frame.columns and frame.index.name == "Date":
        frame = frame.reset_index()
    missing = sorted(set(REQUIRED) - set(frame.columns))
    if missing:
        raise ValueError(f"missing columns: {missing}")
    x = frame.reset_index(drop=True).copy()
    original_rows = len(x)
    x["date"] = pd.to_datetime(x["Date"], errors="coerce").dt.tz_localize(None).dt.normalize()
    market = x["Market"].astype("string").str.strip().map(MARKETS)
    x = x.loc[market.isin(["KOSPI", "KOSDAQ"])].copy()
    market = market.loc[x.index]
    market_rows = len(x)
    x["ticker"] = x["Code"].astype("string").str.strip()
    valid_code = x["ticker"].str.fullmatch(r"\d{1,6}").fillna(False)
    invalid_codes = int((~valid_code).sum())
    x = x.loc[valid_code].copy()
    market = market.loc[x.index]
    x["ticker"] = x["ticker"].str.zfill(6)
    for name in ("Open", "High", "Low", "Close", "Volume", "Amount"):
        x[name] = pd.to_numeric(x[name], errors="coerce")
    required_notna = x[["date", "ticker", "Open", "High", "Low", "Close", "Volume", "Amount"]].notna().all(axis=1)
    year_ok = x["date"].dt.year.eq(year)
    price_ok = x[["Open", "High", "Low", "Close"]].gt(0).all(axis=1)
    range_ok = (x["High"] >= x[["Open", "High", "Low", "Close"]].max(axis=1)) & (x["Low"] <= x[["Open", "High", "Low", "Close"]].min(axis=1))
    volume_ok = (x["Volume"] >= 0) & (x["Amount"] >= 0)
    clean = required_notna & year_ok & price_ok & range_ok & volume_ok
    dropped_quality = int((~(required_notna & price_ok & range_ok & volume_ok)).sum())
    dropped_year = int((~year_ok & required_notna).sum())
    filtered = x.loc[clean]
    market = market.loc[filtered.index]
    result = filtered.rename(columns={
        "Open": "open", "High": "high", "Low": "low", "Close": "close",
        "Volume": "volume", "Amount": "turnover",
    }).loc[:, COLS].copy()
    if result.duplicated(["date", "ticker"]).any():
        raise ValueError("duplicate date and stock code; manual review required")
    result = result.sort_values(["date", "ticker"]).reset_index(drop=True)
    if len(result) == 0:
        raise ValueError(f"no valid market data for {year}")
    return result, {
        "year": year, "source_rows": original_rows, "kospi_kosdaq_rows": market_rows,
        "dropped_invalid_codes": invalid_codes, "dropped_quality_rows": dropped_quality,
        "dropped_wrong_year_rows": dropped_year, "normalized_rows": len(result),
        "zero_volume_or_turnover_rows": int(((result.volume == 0) | (result.turnover == 0)).sum()),
        "unique_sessions": int(result.date.nunique()), "unique_tickers": int(result.ticker.nunique()),
        "date_start": str(result.date.min().date()), "date_end": str(result.date.max().date()),
        "market_rows": {str(k): int(v) for k, v in market.value_counts().items()},
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Download, normalize, and audit KRX-derived historical market data")
    parser.add_argument("--start-year", type=int, default=2017)
    parser.add_argument("--end-year", type=int, default=2026)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--ref", default=DEFAULT_REF, help="pinned commit SHA or master")
    parser.add_argument("--keep-raw", action="store_true", help="keep downloaded Parquet privately")
    args = parser.parse_args(argv)
    if not (1995 <= args.start_year <= args.end_year <= 2100):
        parser.error("invalid years")
    dest = args.output
    dest.mkdir(parents=True, exist_ok=True)
    reports, sessions = [], set()
    for year in range(args.start_year, args.end_year + 1):
        raw = dest / "_raw" / f"marcap-{year}.parquet"
        source_info = download(year, raw, args.ref)
        try:
            normalized, audit = normalize_marcap(pd.read_parquet(raw), year)
        finally:
            if not args.keep_raw:
                raw.unlink(missing_ok=True)
        out = dest / "_private" / f"kswing_prices_{year}.csv.gz"
        out.parent.mkdir(parents=True, exist_ok=True)
        normalized.to_csv(out, index=False, compression="gzip", date_format="%Y-%m-%d")
        sessions.update(pd.Timestamp(date) for date in normalized.date.unique())
        audit.update({
            "source_sha256": source_info["sha256"],
            "source_bytes": source_info["bytes"],
            "normalized_sha256": sha256_file(out),
            "normalized_bytes": out.stat().st_size,
        })
        reports.append(audit)
        print(json.dumps({"year": year, "rows": audit["normalized_rows"], "sessions": audit["unique_sessions"]}), flush=True)
    pd.DataFrame({"date": sorted(sessions)}).to_csv(
        dest / "_private" / "krx_observed_sessions.csv", index=False, date_format="%Y-%m-%d")
    summary = {
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "source": SOURCE, "source_ref": args.ref,
        "years": reports, "total_rows": sum(x["normalized_rows"] for x in reports),
        "total_sessions": len(sessions),
        "limitations": [
            "Survivorship-free coverage is unverified; include delisted security masters",
            "Corporate action adjustment is unverified; handle splits, mergers and delistings",
            "Market filter does not distinguish every preferred share and SPAC",
            "Observed session dates are provisional, not a verified KRX holiday calendar",
            "Zero-volume sessions are preserved to invalidate untradable target windows",
            "Raw prices cannot be redistributed without verifying exchange permissions",
        ],
    }
    summary_file = dest / "marcap_audit_summary.json"
    summary_file.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Audit summary: {summary_file}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
