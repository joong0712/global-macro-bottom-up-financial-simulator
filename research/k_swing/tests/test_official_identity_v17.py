import copy
import pytest
from research.k_swing.official_identity_v17 import reconcile


def response(records, total=None):
    return {"response": {"header": {"resultCode": "00"},
                         "body": {"totalCount": len(records) if total is None else total,
                                  "items": {"item": records}}}}


def row(ticker="005930", isin="KR7005930003", day="20200102", market="KOSPI"):
    return {"basDt": day, "srtnCd": ticker, "isinCd": isin, "mrktCtg": market}


def observed(ticker="005930", day="20200102"):
    return [{"ticker": ticker, "date": day}]


def test_same_day_official_identity_does_not_certify_alpha():
    result = reconcile(response([row()]), observed(), snapshot_day="20200102")
    assert result["matched_identity_only"] == 1
    assert result["blocked_identity"] == 0
    assert not result["ordinary_share_class_verified"]
    assert not result["portfolio_pnl_verified"]
    assert not result["live_orders_allowed"]


def test_missing_or_ambiguous_isin_blocks():
    assert reconcile(response([]), observed(), snapshot_day="20200102")["blocked_identity"] == 1
    ambiguous = response([row(), row(isin="KR7005930004")])
    assert reconcile(ambiguous, observed(), snapshot_day="20200102")["blocked_identity"] == 1


@pytest.mark.parametrize("bad", [
    response([row(day="20200103")]),
    response([row()], total=200),
    response([row(isin="not-isin")]),
    response([row(ticker="00593")]),
    {"response": {"header": {"resultCode": "03"}, "body": {"totalCount": 0, "items": {"item": []}}}},
])
def test_bad_official_source_is_rejected(bad):
    with pytest.raises(ValueError):
        reconcile(bad, observed(), snapshot_day="20200102")


def test_no_future_backfill_and_no_locked_confirmation():
    with pytest.raises(ValueError):
        reconcile(response([row()]), observed(), snapshot_day="20260102")
    with pytest.raises(ValueError):
        reconcile(response([row(day="20210104")]), observed(day="20200102"),
                  snapshot_day="20200102")


def test_duplicate_observed_security_is_not_double_counted():
    with pytest.raises(ValueError):
        reconcile(response([row()]), observed() * 2, snapshot_day="20200102")
