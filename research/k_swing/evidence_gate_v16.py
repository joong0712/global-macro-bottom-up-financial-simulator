"""v1.6 fail-closed investment-evidence audit; never invent missing KRX data.

Separate source authentication, corporate-action completeness, and executable
fill/cost proof. Historical vendor OHLCV and a schema-valid official-event CSV
cannot by themselves certify any of these.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path

REQUIRED = {
    "security_identity": (
        "historical_isin_ticker_market_shareclass_by_session",
        "full_delisted_and_inactive_security_coverage",
        "source_publication_vintage_by_signal_cutoff",
    ),
    "corporate_actions": (
        "official_event_source_record_completeness",
        "split_dividend_merger_rights_adjusted_price_reconciliation",
        "delisting_terminal_cash_and_position_outcomes",
    ),
    "execution_costs": (
        "effective_dated_korean_taxes_and_exchange_fees",
        "opening_auction_fill_and_suspension_limit_rules",
        "portfolio_cash_inventory_reconciliation",
        "impact_slippage_and_participation_stress",
    ),
}

def audit(evidence: dict | None = None) -> dict:
    """Do not promote any checklist item without source-backed review.

    This intentionally treats self-attested booleans as unverified; a verified
    claim needs a nonempty official source ID, accessible source locator,
    evidence as-of timestamp and a separate explicit manual reviewer signoff.
    Even those are only *documentary completeness*, not verified historical
    performance. Nothing here places a trade or unlocks future data.
    """
    e = evidence if evidence is not None else {}
    if not isinstance(e, dict):
        raise ValueError("Evidence must be a JSON object")
    unknown = set(e) - set(REQUIRED)
    if unknown:
        raise ValueError("Unknown evidence domains: " + ", ".join(sorted(unknown)))
    out = {}
    for domain, fields in REQUIRED.items():
        supplied = e.get(domain, {})
        if not isinstance(supplied, dict):
            raise ValueError("Each domain must be an object")
        extra = set(supplied) - set(fields)
        if extra:
            raise ValueError("Unknown evidence fields: " + ", ".join(sorted(extra)))
        checks = {}
        for field in fields:
            entry = supplied.get(field)
            valid = (
                isinstance(entry, dict)
                and isinstance(entry.get("source_record_id"), str)
                and bool(entry["source_record_id"].strip())
                and isinstance(entry.get("source_uri"), str)
                and entry["source_uri"].startswith("https://")
                and isinstance(entry.get("asof_utc"), str)
                and bool(entry["asof_utc"].strip())
                and entry.get("independent_reviewed") is True
            )
            checks[field] = {
                "documentary_evidence_present": bool(valid),
                "status": "DOCUMENTED_REQUIRES_REPRODUCTION" if valid
                          else "BLOCKED_UNVERIFIED",
            }
        out[domain] = checks
    complete = all(c["documentary_evidence_present"]
                   for d in out.values() for c in d.values())
    return {
        "status": "DOCUMENTARY_REVIEW_REQUIRED" if complete
                  else "BLOCKED_MISSING_EXECUTION_OR_PROVENANCE_EVIDENCE",
        "checks": out,
        "missing_count": sum(not c["documentary_evidence_present"]
                             for d in out.values() for c in d.values()),
        "documentary_completeness_is_not_verified_profit": True,
        "independent_2026_confirmation_unlocked": False,
        "real_money_orders_allowed": False,
        "new_data_downloaded": False,
    }


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--evidence", type=Path)
    p.add_argument("--output", type=Path, required=True)
    args = p.parse_args()
    evidence = json.loads(args.evidence.read_text()) if args.evidence else None
    result = audit(evidence)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, ensure_ascii=False))
    print(json.dumps({"status": result["status"],
                      "missing_count": result["missing_count"],
                      "2026_locked": True}))


if __name__ == "__main__":
    main()
