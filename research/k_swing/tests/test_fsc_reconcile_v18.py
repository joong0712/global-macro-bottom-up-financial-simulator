import pytest
from research.k_swing.fsc_reconcile_v18 import reconcile, normalize_short_code


def day(rows):
    return {"date": "20200102", "complete": True, "count": len(rows),
            "records": rows}


def rec(code, isin="KR7005930003", market="KOSPI"):
    return {"basDt": "20200102", "srtnCd": code, "isinCd": isin,
            "mrktCtg": market}


def obs(code):
    return [{"date": "20200102", "ticker": code}]


def test_a_prefixed_normalization():
    assert normalize_short_code("A005930") == "005930"
    assert normalize_short_code("005930") == "005930"
    assert normalize_short_code("A900110") == "900110"


def test_official_foreign_isin_not_discarded():
    result = reconcile(day([rec("A900110", "HK0000057197", "KOSDAQ")]),
                       obs("900110"))
    assert result["identity_only_matches"] == 1
    assert not result["ordinary_share_class_verified"]


def test_ambiguous_official_identity_blocks():
    x = day([rec("005930"), rec("A005930", "KR7005930004")])
    assert reconcile(x, obs("005930"))["blocked"] == 1


def test_unsupported_market_blocks():
    assert reconcile(day([rec("005930", market="KONEX")]),
                     obs("005930"))["blocked"] == 1


def test_missing_and_incomplete_fail_closed():
    assert reconcile(day([]), obs("005930"))["blocked"] == 1
    with pytest.raises(ValueError, match="complete"):
        reconcile({"complete": False}, obs("005930"))
