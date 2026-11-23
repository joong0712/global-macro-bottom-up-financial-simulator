import pytest

from research.k_swing.evidence_gate_v16 import REQUIRED, audit


def test_empty_evidence_fails_closed():
    result = audit()
    assert result["status"].startswith("BLOCKED")
    assert result["missing_count"] == sum(map(len, REQUIRED.values()))
    assert result["real_money_orders_allowed"] is False
    assert result["independent_2026_confirmation_unlocked"] is False


def test_self_attestation_is_not_official_proof():
    claim = {domain: {field: True for field in fields}
             for domain, fields in REQUIRED.items()}
    result = audit(claim)
    assert result["missing_count"] == sum(map(len, REQUIRED.values()))


def test_partial_documentation_is_not_approval():
    result = audit({"security_identity": {
        "historical_isin_ticker_market_shareclass_by_session": {
            "source_record_id": "official-1",
            "source_uri": "https://data.krx.co.kr/official",
            "asof_utc": "2022-01-01T00:00:00Z",
            "independent_reviewed": True,
        }
    }})
    assert result["missing_count"] == sum(map(len, REQUIRED.values())) - 1
    assert result["status"].startswith("BLOCKED")


def test_even_complete_claims_do_not_unlock_trading_or_holdout():
    record = {"source_record_id": "official-1",
              "source_uri": "https://data.krx.co.kr/official",
              "asof_utc": "2022-01-01T00:00:00Z",
              "independent_reviewed": True}
    claim = {domain: {field: record for field in fields}
             for domain, fields in REQUIRED.items()}
    result = audit(claim)
    assert result["status"] == "DOCUMENTARY_REVIEW_REQUIRED"
    assert result["missing_count"] == 0
    assert result["documentary_completeness_is_not_verified_profit"]
    assert result["real_money_orders_allowed"] is False
    assert result["independent_2026_confirmation_unlocked"] is False


def test_unrecognized_claim_rejected():
    with pytest.raises(ValueError, match="Unknown evidence"):
        audit({"profit_guaranteed": True})
