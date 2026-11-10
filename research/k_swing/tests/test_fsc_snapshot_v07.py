"""Official FSC source adapter: no key, no false full-history, safe errors."""
import io
import json
import pytest
from research.k_swing.fsc_snapshot_v07 import get_fsc_listing_day


class HttpResponse:
    def __init__(self, payload): self.bytes=json.dumps(payload).encode("utf-8")
    def __enter__(self): return self
    def __exit__(self, exc_type, exc_val, tb): return None
    def read(self): return self.bytes


def test_no_key_fails_before_call(monkeypatch):
    monkeypatch.delenv("FSC_STOCK_API_KEY",raising=False)
    with pytest.raises(RuntimeError,match="not connected"):
        get_fsc_listing_day("20230102")


def test_real_schema_simulator_one_day_is_not_complete_history():
    def fake_opener(request,timeout):
        assert b"neverlog" not in bytes(str(request.full_url),"utf-8")
        return HttpResponse({"response":{
            "header":{"resultCode":"00"},"body":{
                "totalCount":1,"items":{"item":[{
                    "basDt":"20230102","isinCd":"KR7005930003",
                    "srtnCd":"005930","itmsNm":"TEST EXAMPLE",
                }]}
            }
        }})
    frame,meta=get_fsc_listing_day("20230102",key="example-only",opener=fake_opener)
    assert len(frame)==1
    assert not meta["historical_delisting_coverage_verified"]
    assert meta["status"].startswith("OFFICIAL_ONE_DAY_REFERENCE")


def test_locked_future_date_rejected_even_if_key_exists():
    with pytest.raises(ValueError,match="locked"):
        get_fsc_listing_day("20260102",key="example")


def test_wrong_snapshot_date_refused():
    def fake(request,timeout):
        return HttpResponse({"response":{
          "header":{"resultCode":"00"},"body":{
              "totalCount":1,"items":{"item":[{
                  "basDt":"20230103","isinCd":"KR7005930003","srtnCd":"005930"
              }]}
          }
        }})
    with pytest.raises(ValueError,match="wrong"):
        get_fsc_listing_day("20230102",key="demo",opener=fake)
