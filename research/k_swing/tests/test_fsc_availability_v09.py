"""Reference basDt T must not sneak into a T-close trading decision."""
import pandas as pd
import pytest
from research.k_swing.fsc_availability_v09 import fsc_snapshot_signal_gate


def data():
    cal=pd.bdate_range("2022-01-03",periods=10)
    signals=pd.DataFrame({"date":[cal[0],cal[1]],"ticker":["005930","005930"]})
    refs=pd.DataFrame({
        "basDt":["20220103","20220104"],"srtnCd":["005930","005930"],
        "isinCd":["KR7005930003"]*2,
        "first_public_at":["2022-01-04T13:01:00+09:00",
                           "2022-01-05T13:01:00+09:00"],
        "historical_vintage_observed_at":["2022-01-04T13:02:00+09:00",
                                          "2022-01-05T13:02:00+09:00"],
    })
    return cal,signals,refs


def test_same_day_reference_cannot_be_used_at_same_day_close():
    cal,s,r=data()
    joined,audit=fsc_snapshot_signal_gate(s,r,cal)
    assert len(joined)==2
    assert joined.signal_time_reference_verified_available.eq(False).all()
    assert audit["historical_reference_admissible_at_signal_T"]==0


def test_backfilled_vintage_fetched_now_is_not_historical_publication():
    cal,s,r=data()
    r.loc[0,"historical_vintage_observed_at"]="2026-11-11T05:00:00+09:00"
    joined,_=fsc_snapshot_signal_gate(s,r,cal)
    assert not joined.signal_time_reference_verified_available.any()


def test_malformed_publication_timestamp_is_rejected():
    cal,s,r=data()
    r.loc[0,"first_public_at"]="2022-01-03 14:00"
    with pytest.raises(ValueError,match="timezone-aware"):
        fsc_snapshot_signal_gate(s,r,cal)


def test_future_holdout_reference_rejected():
    cal,s,r=data()
    r.loc[0,"basDt"]="20260103"
    with pytest.raises(ValueError,match="locked"):
        fsc_snapshot_signal_gate(s,r,cal)
