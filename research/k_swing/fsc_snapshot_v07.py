"""Optional authenticated FSC historical listed-security snapshot retriever.

Official catalog: https://www.data.go.kr/en/data/15094775/openapi.do
Endpoint: https://apis.data.go.kr/1160100/GetKrxListedInfoService_V2/getItemInfo_V2

Requires an authorized serviceKey from the FSC_STOCK_API_KEY environment
variable. No key means NO FETCH and never a fake "complete" universe.
Only raw snapshots in private local disk; NEVER upload them to open CI artifacts.
Public source terms and attribution/noncommercial restrictions must be checked.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

OFFICIAL_URL = (
    "https://apis.data.go.kr/1160100/"
    "GetKrxListedInfoService_V2/getItemInfo_V2"
)


def _safe_api_json(url: str, opener=urllib.request.urlopen) -> dict:
    """Fail without printing the URL (it contains the confidential key)."""
    request = urllib.request.Request(
        url, headers={"User-Agent": "KSWING-Research-Historical-Reference/0.7"})
    try:
        with opener(request, timeout=35) as response:
            content = response.read()
        return json.loads(content.decode("utf-8-sig"))
    except (urllib.error.HTTPError, urllib.error.URLError,
            TimeoutError, ValueError, UnicodeError) as exc:
        raise RuntimeError(
            f"FSC official API call failed ({type(exc).__name__}); "
            "check key, entitlement, date and JSON response locally. "
            "Credential URL deliberately hidden."
        ) from None


def get_fsc_listing_day(
    basdt: str, *,
    key: str | None = None,
    opener=urllib.request.urlopen,
    max_pages: int = 50,
) -> tuple[pd.DataFrame, dict]:
    """Retrieve a single historical as-of date; do not assume whole history."""
    if not re.fullmatch(r"20(?:1\d|2[0-3])(?:0[1-9]|1[0-2])(?:0[1-9]|[12]\d|3[01])", basdt):
        raise ValueError("one YYYYMMDD in 2010-2023 required; 2024-2026 locked")
    if key is None:
        key = os.getenv("FSC_STOCK_API_KEY")
    if not key or not key.strip():
        raise RuntimeError("FSC_STOCK_API_KEY not connected; official snapshot NOT fetched")
    if max_pages < 1 or max_pages > 100:
        raise ValueError("invalid max_pages")
    rows=[]
    total=None
    page=1
    page_size=1000
    while True:
        params={
            "serviceKey":key.strip(),"resultType":"json","basDt":basdt,
            "pageNo":str(page),"numOfRows":str(page_size),
        }
        url=OFFICIAL_URL+"?"+urllib.parse.urlencode(params)
        payload=_safe_api_json(url, opener=opener)
        response=payload.get("response") or {}
        header=response.get("header") or {}
        if str(header.get("resultCode", "00")) not in ("00","0"):
            raise RuntimeError("FSC API denied response, no official coverage certified")
        body=response.get("body") or {}
        items=body.get("items") or {}
        page_items=items.get("item",[]) if isinstance(items,dict) else []
        if isinstance(page_items,dict):
            page_items=[page_items]
        if not isinstance(page_items,list):
            raise ValueError("invalid FSC item shape")
        rows.extend(page_items)
        try:
            total=int(body.get("totalCount",0))
        except (ValueError,TypeError):
            raise ValueError("missing FSC totalCount")
        if len(rows)>=total:
            break
        if not page_items or page>=max_pages:
            raise RuntimeError("official snapshot pagination incomplete; reject coverage")
        page+=1
    if total==0:
        raise ValueError("zero-row response is not official completeness")
    data=pd.DataFrame(rows)
    if not {"basDt","isinCd","srtnCd"}.issubset(data.columns):
        raise ValueError("missing dated ISIN or ticker fields in official snapshot")
    if not data.basDt.astype("string").eq(basdt).all():
        raise ValueError("API returned wrong historical as-of dates")
    if not data.isinCd.astype("string").str.fullmatch(r"KR[A-Z0-9]{10}").all():
        raise ValueError("invalid official ISIN values")
    if data.duplicated(["basDt","isinCd"]).any():
        raise ValueError("duplicate ISIN on snapshot date")
    # Very important: one as-of date is NOT an audited history of disappeared
    # securities, mergers, splits, and multiple decades of trading.
    audit={
        "status":"OFFICIAL_ONE_DAY_REFERENCE_SNAPSHOT_NOT_COMPLETE_HISTORY",
        "basDt":basdt,"records":len(data),
        "pages":page,"reported_total_count":total,
        "source":"FSC KRX listed information, authenticated authorized API",
        "fsc_endpoint_origin":"apis.data.go.kr",
        "historical_delisting_coverage_verified":False,
        "corporate_action_adjustments_verified":False,
        "usage_license_requires_review":True,
        "2026_confirmation_touched":False,
        "retrieved_utc":datetime.now(timezone.utc).isoformat(),
    }
    return data,audit


def main():
    p=argparse.ArgumentParser(description="Authorized FSC historical snapshot, private only")
    p.add_argument("--basdt",required=True)
    p.add_argument("--output-private",type=Path,required=True)
    args=p.parse_args()
    frame,meta=get_fsc_listing_day(args.basdt)
    args.output_private.mkdir(parents=True,exist_ok=True)
    raw=args.output_private / f"fsc_isin_snapshot_{args.basdt}.csv.gz"
    frame.to_csv(raw,index=False,compression="gzip")
    meta["sha256_private_csv"] = hashlib.sha256(raw.read_bytes()).hexdigest()
    (args.output_private/f"fsc_snapshot_{args.basdt}_manifest.json").write_text(
        json.dumps(meta,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps({k:meta[k] for k in ("status","basDt","records","historical_delisting_coverage_verified")},
                     ensure_ascii=False))


if __name__=="__main__":
    main()
