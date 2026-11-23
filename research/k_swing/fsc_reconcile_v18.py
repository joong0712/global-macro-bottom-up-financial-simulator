"""Reconcile complete FSC one-day records to six-digit research symbols.

Never silently strip non-A prefixes or assume foreign ISIN is invalid.
Do not infer ordinary-share type from ticker, market or ISIN alone.
"""
from __future__ import annotations
import argparse
import json
import re
from pathlib import Path
from .fsc_ingest_v18 import CODE, ISIN

def normalize_short_code(code: str) -> str | None:
    x = str(code).strip()
    if not CODE.fullmatch(x):
        raise ValueError("Invalid official short code")
    if re.fullmatch(r"\d{6}", x):
        return x
    if re.fullmatch(r"A\d{6}", x):
        return x[1:]
    # Other A-prefixed foreign codes are NOT silently mapped.
    return None


def reconcile(day_data: dict, observed: list[dict]) -> dict:
    if day_data.get("complete") is not True:
        raise ValueError("Official daily response must be complete")
    day = day_data.get("date")
    if not re.fullmatch(r"20(?:1[7-9]|2[0-2])\d{4}", str(day)):
        raise ValueError("Research-era date only")
    records = day_data.get("records")
    if not isinstance(records, list) or len(records) != day_data.get("count"):
        raise ValueError("Official row count mismatch")
    mapping = {}
    for row in records:
        if str(row.get("basDt")) != day:
            raise ValueError("Stale official record")
        code = normalize_short_code(row.get("srtnCd"))
        isin = str(row.get("isinCd", ""))
        if not ISIN.fullmatch(isin):
            raise ValueError("Invalid official ISIN")
        if code is None:
            continue
        mapping.setdefault(code, set()).add((isin, str(row.get("mrktCtg", "")).upper()))
    if not isinstance(observed, list):
        raise ValueError("Observed rows must be list")
    matched = blocked = 0
    seen = set()
    for row in observed:
        ticker = str(row.get("ticker", ""))
        if not re.fullmatch(r"\d{6}", ticker) or ticker in seen:
            raise ValueError("Duplicate or invalid observed symbol")
        seen.add(ticker)
        if str(row.get("date")) != day:
            raise ValueError("Different observed and official date")
        ids = mapping.get(ticker, set())
        if len(ids) != 1 or next(iter(ids))[1] not in ("KOSPI", "KOSDAQ"):
            blocked += 1
        else:
            matched += 1
    return {
        "date": day, "observed_count": len(observed),
        "identity_only_matches": matched, "blocked": blocked,
        "ordinary_share_class_verified": False,
        "delisted_universe_verified": False,
        "corporate_actions_verified": False,
        "point_in_time_publication_verified": False,
        "pnl_verified": False, "live_orders_allowed": False,
    }


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--private-day-json", type=Path, required=True)
    p.add_argument("--private-observed-json", type=Path, required=True)
    p.add_argument("--aggregate-output", type=Path, required=True)
    args = p.parse_args()
    result = reconcile(json.loads(args.private_day_json.read_text()),
                       json.loads(args.private_observed_json.read_text()))
    args.aggregate_output.parent.mkdir(parents=True, exist_ok=True)
    args.aggregate_output.write_text(json.dumps(result, indent=2))
    print(json.dumps(result))


if __name__ == "__main__":
    main()
