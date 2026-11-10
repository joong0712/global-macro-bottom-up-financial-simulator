"""v0.7 official KRX/KIND/FSC corporate-action and delisting verification gate.

A website listing an API is NOT equivalent to acquiring historical verified
security event records. Fail closed when authenticated official data is absent.
This code does not call external APIs, infer splits, or silently modify prices.
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

import pandas as pd

OFFICIAL_SOURCES = {
    "KRX": ("openapi.krx.co.kr", "data.krx.co.kr"),
    "KIND": ("kind.krx.co.kr",),
    "FSC": ("data.go.kr", "apis.data.go.kr"),
}
KNOWN_EVENTS = {
    "split", "reverse_split", "stock_dividend", "rights_issue",
    "capital_reduction", "merger", "spin_off", "delisting", "listing",
    "suspension", "resumption", "identifier_change",
}
REQUIRED = {
    "security_id", "ticker", "event_type", "effective_date",
    "first_public_at", "official_source", "official_url", "source_record_id",
}


def validate_event_records(events: pd.DataFrame) -> pd.DataFrame:
    """Accept only documented official records, keyed by historical ISIN."""
    absent = REQUIRED - set(events.columns)
    if absent:
        raise ValueError(f"missing required official event columns: {sorted(absent)}")
    data = events.copy()
    if data.empty:
        raise ValueError("empty file is not verified corporate action coverage")
    if data[list(REQUIRED)].isna().any().any():
        raise ValueError("official source/identity/publication metadata must be complete")
    data["security_id"] = data.security_id.astype(str).str.strip()
    data["ticker"] = data.ticker.astype(str).str.zfill(6)
    if not data.security_id.str.fullmatch(r"KR[A-Z0-9]{10}").all():
        raise ValueError("historical Korean ISIN required, not a ticker-only join")
    if not data.ticker.str.fullmatch(r"\d{6}").all():
        raise ValueError("invalid six-digit Korean ticker")
    if not data.event_type.isin(KNOWN_EVENTS).all():
        raise ValueError("unrecognized official event type")
    if not data.official_source.isin(OFFICIAL_SOURCES).all():
        raise ValueError("unsupported source; use KRX/KIND/FSC provenance")
    for record in data.itertuples(index=False):
        url = urlparse(str(record.official_url))
        if url.scheme != "https" or url.hostname not in OFFICIAL_SOURCES[record.official_source]:
            raise ValueError("event source URL does not belong to declared official origin")
        ts = str(record.first_public_at)
        if not (ts.endswith("Z") or (len(ts) >= 6 and ts[-6] in "+-" and ts[-3] == ":")):
            raise ValueError("first_public_at must be timezone-aware (true publication, not filing period)")
    data["effective_date"] = pd.to_datetime(data.effective_date, errors="raise").dt.normalize()
    if data.effective_date.isna().any():
        raise ValueError("missing effective date")
    data["_first_public_utc"] = pd.to_datetime(data.first_public_at, utc=True, format="mixed", errors="raise")
    if data.duplicated(["official_source", "source_record_id"]).any():
        raise ValueError("official source record id is not unique")
    # Known historical signal admissibility is checked for each signal timestamp,
    # not by assuming an effective date means information was already public.
    return data


def asof_events(events: pd.DataFrame, signal_date: str, cutoff: str = "15:30") -> pd.DataFrame:
    """Make late-published filings unavailable until a later signal session."""
    if not pd.Series([cutoff]).str.fullmatch(r"(?:[01]\d|2[0-3]):[0-5]\d").all():
        raise ValueError("invalid time")
    dt = pd.Timestamp(signal_date)
    if dt.tzinfo is not None:
        raise ValueError("signal_date must be exchange-local date without timezone")
    hour, minute = map(int, cutoff.split(":"))
    cutoff_utc = (dt.normalize().tz_localize("Asia/Seoul") +
                  pd.Timedelta(hours=hour, minutes=minute)).tz_convert("UTC")
    verified = validate_event_records(events)
    return verified.loc[verified._first_public_utc.le(cutoff_utc)].copy()


def official_coverage_report(events_file: Path | None,
                             missing_codes: pd.DataFrame | None = None) -> dict:
    """No fabricated 'verified' status when API keys/event CSV are absent."""
    report = {
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "status": "BLOCKED_OFFICIAL_HISTORY_NOT_PROVIDED",
        "corporate_action_adjusted_prices_verified": False,
        "delisting_outcomes_verified": False,
        "full_point_in_time_universe_verified": False,
        "official_sources_required": list(OFFICIAL_SOURCES),
        "official_input_supplied": bool(events_file),
        "candidate_inactive_symbols_are_not_confirmed_delistings": True,
        "data_license_verified": False,
        "2026_confirmation_touched": False,
        "notes": [
            "KRX Open API service catalog alone does NOT provide authenticated data in this run.",
            "FSC stock-issuance API may be application-key gated and its reuse license must be reviewed.",
            "Ticker code is not a durable historical security identity; require genuine historical ISIN.",
            "An event manifest alone cannot certify completeness of all past corporate actions/delistings.",
        ],
    }
    if missing_codes is not None:
        if not {"ticker", "last_observed_date"}.issubset(missing_codes):
            raise ValueError("candidate list must show ticker and last observed date")
        report["unconfirmed_inactive_candidates"] = len(missing_codes)
    if events_file is not None:
        verified = validate_event_records(pd.read_csv(events_file, dtype={"ticker": "string"}))
        report["schema_valid_official_event_rows"] = len(verified)
        report["verified_event_source_counts"] = {
            str(k): int(v) for k,v in verified.official_source.value_counts().items()
        }
        report["status"] = "RECEIVED_EVENT_SCHEMA_VALID_BUT_UNIVERSE_AND_ADJUSTMENTS_UNCERTIFIED"
    return report


def main():
    p = argparse.ArgumentParser(description="Official KRX/KIND/FSC completeness GATE, fail-closed")
    p.add_argument("--events", type=Path, default=None,
                   help="Authorized official historical event CSV; never fabricated")
    p.add_argument("--output", type=Path, required=True)
    args = p.parse_args()
    report = official_coverage_report(args.events)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"status": report["status"],
                      "historical_adjustments_certified": False,
                      "historical_delistings_certified": False}, ensure_ascii=False))


if __name__ == "__main__":
    main()
