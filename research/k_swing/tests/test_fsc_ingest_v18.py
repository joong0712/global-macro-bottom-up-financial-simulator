import json
from urllib.parse import parse_qs, urlparse
import pytest
from research.k_swing.fsc_ingest_v18 import collect_one_day, parse_page


def response(rows, total):
    return {"response": {"header": {"resultCode": "00"},
                         "body": {"totalCount": total, "items": {"item": rows}}}}


def record(ticker, isin="KR7005930003", day="20200102"):
    return {"basDt": day, "srtnCd": ticker, "isinCd": isin,
            "mrktCtg": "KOSPI"}


def test_complete_two_pages_and_aprefix():
    requests = []
    def fetch(url):
        params = parse_qs(urlparse(url).query)
        requests.append(params)
        page = int(params["pageNo"][0])
        if page == 1:
            return response([record("005930")], 2)
        return response([record("A900110", "HK0000057197")], 2)
    result = collect_one_day("20200102", "TEST-SECRET", rows_per_page=1,
                             fetch=fetch)
    assert result["count"] == 2 and result["complete"]
    assert len(requests) == 2
    assert all(r["basDt"] == ["20200102"] for r in requests)


def test_empty_valid_official_day():
    x = collect_one_day("20200102", "test",
                        fetch=lambda _: response([], 0))
    assert x["count"] == 0


def test_incomplete_pagination_fails_closed():
    def fetch(url):
        page = int(parse_qs(urlparse(url).query)["pageNo"][0])
        return response([record("005930")] if page == 1 else [], 2)
    with pytest.raises(ValueError, match="Incomplete"):
        collect_one_day("20200102", "test", fetch=fetch)


def test_duplicate_pages_fails_closed():
    with pytest.raises(ValueError, match="Duplicate"):
        collect_one_day("20200102", "test", rows_per_page=1,
                        fetch=lambda _: response([record("005930")], 2))


def test_official_foreign_isin_is_accepted():
    rows, count = parse_page(response(
        [record("A900110", "HK0000057197")], 1), expected_date="20200102")
    assert len(rows) == count == 1


def test_future_and_missing_credentials_rejected():
    with pytest.raises(ValueError, match="2026 locked"):
        collect_one_day("20260102", "test", fetch=lambda _: response([], 0))
    with pytest.raises(ValueError, match="FSC_SERVICE_KEY"):
        collect_one_day("20200102", "", fetch=lambda _: response([], 0))


def test_stale_response_and_permission_denied_rejected():
    with pytest.raises(ValueError, match="Stale"):
        parse_page(response([record("005930", day="20200103")], 1),
                   expected_date="20200102")
    bad = response([], 0)
    bad["response"]["header"]["resultCode"] = "30"
    with pytest.raises(ValueError, match="permission"):
        parse_page(bad, expected_date="20200102")
