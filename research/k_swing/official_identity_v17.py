"""Fail-closed reconciliation of official historical KRX security identity.

Consumes *user-provided* FSC KRX listed-info V2 JSON responses; no network,
keys or external secrets. Only authoritative daily as-of snapshots may be
used to qualify a trading day's security identity. No future backfill.

Official API documentation:
https://www.data.go.kr/en/data/15094775/openapi.do
"""
from __future__ import annotations
import argparse
import json
import re
from collections import defaultdict
from datetime import date
from pathlib import Path

SIX_DIGITS = re.compile(r"^\d{6}$")
ISIN = re.compile(r"^KR[A-Z0-9]{10}$")
MARKETS = ("KOSPI", "KOSDAQ")
REQUIRED = ("basDt", "srtnCd", "isinCd", "mrktCtg")
RESEARCH_END = date(2022, 12, 31)


def _date(value: str) -> date:
    if not isinstance(value, str) or not re.fullmatch(r"\d{8}", value):
        raise ValueError("Invalid official YYYYMMDD date")
    return date.fromisoformat(f"{value[:4]}-{value[4:6]}-{value[6:]}")


def _extract(response: dict) -> list[dict]:
    """Read the published data.go.kr JSON envelope without guessing fields."""
    if not isinstance(response, dict):
        raise ValueError("Official response must be JSON object")
    header = response.get("response", {}).get("header", {})
    if str(header.get("resultCode", "")) not in ("00", "0"):
        raise ValueError("Official API response not successful")
    body = response["response"]["body"]
    items = body.get("items")
    if not isinstance(items, dict) or "item" not in items:
        raise ValueError("Missing official item collection")
    records = items["item"]
    if isinstance(records, dict):
        records = [records]
    if not isinstance(records, list):
        raise ValueError("Invalid official item list")
    if int(body.get("totalCount", -1)) != len(records):
        # Prevent silent truncated pagination from being mistaken for
        # a complete historical daily universe.
        raise ValueError("Incomplete paginated official response")
    return records


def reconcile(
    official_response: dict,
    observed: list[dict],
    *,
    snapshot_day: str,
) -> dict:
    """Compare observed symbols against same-day official records.

    A same-day snapshot is essential; a present-day listing cannot certify
    a 2019 security, delisted name or ticker reuse. Missing records BLOCK,
    not silently drop the ticker. KOSPI/KOSDAQ ordinary equity class must
    be independently verified: this API does not guarantee that attribute.
    """
    day = _date(snapshot_day)
    if day > RESEARCH_END or day < date(2017, 1, 1):
        raise ValueError("Only locked 2017–2022 research-era dates")
    rows = _extract(official_response)
    identity = defaultdict(set)
    for row in rows:
        if not isinstance(row, dict) or not all(k in row for k in REQUIRED):
            raise ValueError("Official row missing required fields")
        if _date(row["basDt"]) != day:
            raise ValueError("Official row is not an as-of daily snapshot")
        ticker = str(row["srtnCd"]).strip()
        isin = str(row["isinCd"]).strip()
        market = str(row["mrktCtg"]).strip().upper()
        if not SIX_DIGITS.fullmatch(ticker) or not ISIN.fullmatch(isin):
            raise ValueError("Invalid official ticker or ISIN")
        identity[ticker].add((isin, market))
    if not isinstance(observed, list):
        raise ValueError("Observed rows must be list")
    checks = []
    seen = set()
    for item in observed:
        if not isinstance(item, dict) or "ticker" not in item or "date" not in item:
            raise ValueError("Missing observed ticker or date")
        if _date(str(item["date"])) != day:
            raise ValueError("Observed trade date differs from official snapshot")
        ticker = str(item["ticker"]).strip()
        if ticker in seen or not SIX_DIGITS.fullmatch(ticker):
            raise ValueError("Duplicate or invalid observed ticker")
        seen.add(ticker)
        candidates = identity.get(ticker, set())
        if len(candidates) != 1:
            status = "BLOCKED_MISSING_OR_AMBIGUOUS_OFFICIAL_IDENTITY"
            isin = None
        else:
            isin, market = next(iter(candidates))
            status = ("IDENTITY_ONLY_PENDING_SHARE_CLASS_AND_ACTIONS"
                      if market in MARKETS
                      else "BLOCKED_UNSUPPORTED_MARKET")
        checks.append({"ticker": ticker, "status": status,
                       "official_isin": isin})
    return {
        "snapshot_day": snapshot_day,
        "official_records": len(rows),
        "observed": len(checks),
        "matched_identity_only": sum(
            x["status"] == "IDENTITY_ONLY_PENDING_SHARE_CLASS_AND_ACTIONS"
            for x in checks),
        "blocked_identity": sum(x["status"].startswith("BLOCKED") for x in checks),
        "ordinary_share_class_verified": False,
        "delisted_security_universe_verified": False,
        "issuer_actions_verified": False,
        "portfolio_pnl_verified": False,
        "live_orders_allowed": False,
        "checks": checks,
    }


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--official-json", type=Path, required=True)
    p.add_argument("--observed-json", type=Path, required=True)
    p.add_argument("--snapshot-day", required=True)
    p.add_argument("--output", type=Path, required=True)
    args = p.parse_args()
    result = reconcile(json.loads(args.official_json.read_text()),
                       json.loads(args.observed_json.read_text()),
                       snapshot_day=args.snapshot_day)
    # Do not publish ticker-level checks to CI artifacts.
    public = {k: v for k, v in result.items() if k != "checks"}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(public, indent=2))
    print(json.dumps(public))


if __name__ == "__main__":
    main()
