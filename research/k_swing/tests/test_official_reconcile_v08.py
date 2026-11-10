"""Never invent missing delistings, splits or date/ISIN reference mappings."""
import pandas as pd
import pytest
from research.k_swing.official_reconcile_v08 import reconcile_official_snapshots


def prices():
    return pd.DataFrame({"date":["2021-01-04","2021-01-05","2021-01-04"],
                         "ticker":["005930","005930","000660"],
                         "close":[100,103,90]})


def fsc():
    return pd.DataFrame({"basDt":["20210104","20210104"],
                         "srtnCd":["005930","000660"],
                         "isinCd":["KR7005930003","KR7000660001"]})


def test_no_data_reports_blocked_with_no_false_certification():
    matched,report=reconcile_official_snapshots(prices(),None)
    assert matched.security_id.isna().all()
    assert not report["delisting_outcomes_verified"]
    assert report["status"].startswith("OFFICIAL_COVERAGE")
    assert not report["price_adjustments_verified"]


def test_exact_date_join_never_forward_fills_missing_day():
    matched,report=reconcile_official_snapshots(prices(),fsc())
    assert report["same_day_verified_isin_matches"]==2
    assert report["missing_exact_day_isin_matches"]==1
    assert not report["all_dates_have_reference_snapshots"]
    assert matched.loc[matched.date.eq(pd.Timestamp("2021-01-05")),
                       "security_id"].isna().all()


def test_ticker_reuse_detected_but_never_silently_merged():
    snap=pd.concat([fsc(),pd.DataFrame([{
        "basDt":"20210105","srtnCd":"005930","isinCd":"KR7999999998"}])],
        ignore_index=True)
    _,report=reconcile_official_snapshots(prices(),snap)
    assert report["ticker_codes_with_multiple_official_isins_across_dates"]==1
    assert not report["full_historical_ordinary_share_universe_verified"]


def test_2026_holdout_is_locked_even_for_reference_records():
    s=fsc()
    s.loc[0,"basDt"]="20260105"
    with pytest.raises(ValueError,match="holdout"):
        reconcile_official_snapshots(prices(),s)


def test_wrong_isin_or_double_identity_rejected():
    s=fsc();s.loc[0,"isinCd"]="005930"
    with pytest.raises(ValueError,match="ISIN"):
        reconcile_official_snapshots(prices(),s)
    s=fsc()
    s.loc[1,"srtnCd"]="005930"
    with pytest.raises(ValueError,match="multiple"):
        reconcile_official_snapshots(prices(),s)
