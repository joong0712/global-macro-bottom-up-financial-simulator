"""Official data gate must never pretend suspicious observations prove delistings."""
import pandas as pd
import pytest
from research.k_swing.official_events_v07 import (
    official_coverage_report, validate_event_records, asof_events,
)


def sample():
    return pd.DataFrame([{
        "security_id":"KR7005930003",
        "ticker":"005930", "event_type":"split",
        "effective_date":"2022-06-15",
        "first_public_at":"2022-06-14T16:00:00+09:00",
        "official_source":"KIND",
        "official_url":"https://kind.krx.co.kr/disclosure/details.do",
        "source_record_id":"TEST_EXAMPLE_ONLY_NOT_AN_ACTUAL_EVENT",
    }])


def test_no_official_access_never_certifies_split_or_delisting():
    r=official_coverage_report(None)
    assert r["status"].startswith("BLOCKED")
    assert not r["corporate_action_adjusted_prices_verified"]
    assert not r["delisting_outcomes_verified"]


def test_asof_after_close_must_not_leak():
    s=sample()
    assert asof_events(s,"2022-06-14").empty
    assert len(asof_events(s,"2022-06-15"))==1


def test_fake_source_or_ambiguous_ticker_history_refused():
    x=sample()
    x.loc[0,"official_url"]="https://example.com"
    with pytest.raises(ValueError,match="URL"):
        validate_event_records(x)
    x=sample()
    x.loc[0,"security_id"]="005930"
    with pytest.raises(ValueError,match="ISIN"):
        validate_event_records(x)


def test_event_file_schema_alone_does_not_certify_historical_coverage(tmp_path):
    p=tmp_path/"events.csv"
    sample().to_csv(p,index=False)
    r=official_coverage_report(p)
    assert r["status"].startswith("RECEIVED")
    assert not r["corporate_action_adjusted_prices_verified"]
    assert not r["full_point_in_time_universe_verified"]
