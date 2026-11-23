"""FSC KRX Listed Info V2, authenticated ingestion of one historical day.

Official public-data terms are non-commercial / attribution / no derivatives.
Never publish or redistribute raw API rows, keys or symbol-level identities.
This is a historical-identity research tool, NOT permission for live trading.
"""
from __future__ import annotations
import argparse
import json
import os
import re
import urllib.parse
import urllib.request
from datetime import date
from pathlib import Path

URL = "https://apis.data.go.kr/1160100/GetKrxListedInfoService_V2/getItemInfo_V2"
# The FSC short code can be A-prefixed; foreign-listed ISINs need not start KR.
CODE = re.compile(r"^(?:A)?[0-9A-Z]{6}$")
ISIN = re.compile(r"^[A-Z]{2}[A-Z0-9]{9}[0-9]$")
MAX_PAGES = 20


def parse_page(raw: dict, *, expected_date: str) -> tuple[list[dict], int]:
    """Validate one JSON page, including legitimate empty responses."""
    if not isinstance(raw, dict):
        raise ValueError("Invalid API response")
    response = raw.get("response")
    if not isinstance(response, dict):
        raise ValueError("Missing response envelope")
    header = response.get("header", {})
    if str(header.get("resultCode", "")) not in ("00", "0"):
        raise ValueError("API error or permission denied")
    body = response.get("body")
    if not isinstance(body, dict):
        raise ValueError("Missing body")
    total = int(body.get("totalCount", -1))
    if total < 0:
        raise ValueError("Missing total count")
    items = body.get("items")
    if items is None or items == "":
        rows = []
    elif isinstance(items, dict):
        rows = items.get("item", [])
    else:
        raise ValueError("Unexpected items structure")
    if isinstance(rows, dict):
        rows = [rows]
    if not isinstance(rows, list):
        raise ValueError("Invalid item array")
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("Invalid item")
        if not {"basDt", "srtnCd", "isinCd", "mrktCtg"}.issubset(row):
            raise ValueError("Missing official fields")
        if str(row["basDt"]) != expected_date:
            raise ValueError("Stale/future historical response")
        if not CODE.fullmatch(str(row["srtnCd"]).strip()):
            raise ValueError("Unrecognized short code")
        if not ISIN.fullmatch(str(row["isinCd"]).strip()):
            raise ValueError("Invalid 12-character ISIN")
    return rows, total


def collect_one_day(
    day: str, key: str, *, rows_per_page: int = 1000,
    fetch=None,
) -> dict:
    """Read every page for exactly one old day, fail on missing/overlap.

    No keys/rows emitted to stdout. Caller must store raw results privately,
    and verify source vintage, market type, delisting and issuer events later.
    """
    if not re.fullmatch(r"\d{8}", day):
        raise ValueError("YYYYMMDD required")
    d = date.fromisoformat(f"{day[:4]}-{day[4:6]}-{day[6:]}")
    if not date(2017, 1, 1) <= d <= date(2022, 12, 31):
        raise ValueError("Only 2017-2022 research era; 2026 locked")
    if not key or not key.strip():
        raise ValueError("FSC_SERVICE_KEY not configured")
    if not 1 <= rows_per_page <= 1000:
        raise ValueError("Invalid page size")
    if fetch is None:
        def fetch(url):
            with urllib.request.urlopen(url, timeout=20) as stream:
                return json.load(stream)
    all_rows, expected_total, seen = [], None, set()
    for page in range(1, MAX_PAGES + 1):
        url = URL + "?" + urllib.parse.urlencode({
            "serviceKey": key, "numOfRows": rows_per_page, "pageNo": page,
            "resultType": "json", "basDt": day,
        })
        # Avoid logging the URL; it contains a secret.
        rows, total = parse_page(fetch(url), expected_date=day)
        if expected_total is None:
            expected_total = total
        if expected_total != total:
            raise ValueError("Inconsistent totalCount across pages")
        for row in rows:
            ident = (str(row["srtnCd"]), str(row["isinCd"]))
            if ident in seen:
                raise ValueError("Duplicate official row across pages")
            seen.add(ident)
            all_rows.append(row)
        if len(all_rows) == expected_total:
            return {"date": day, "count": len(all_rows),
                    "records": all_rows, "complete": True}
        if not rows or len(all_rows) > expected_total:
            raise ValueError("Incomplete official pagination")
    raise ValueError("Official pagination exceeded conservative page cap")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--day", required=True)
    p.add_argument("--private-output", type=Path, required=True)
    args = p.parse_args()
    key = os.environ.get("FSC_SERVICE_KEY", "")
    result = collect_one_day(args.day, key)
    args.private_output.parent.mkdir(parents=True, exist_ok=True)
    args.private_output.write_text(json.dumps(result, ensure_ascii=False))
    args.private_output.chmod(0o600)
    print(json.dumps({"status": "OFFICIAL_DAY_FETCHED_UNVERIFIED_VINTAGE",
                      "date": args.day, "records": result["count"],
                      "raw_published": False, "2026_locked": True}))


if __name__ == "__main__":
    main()
