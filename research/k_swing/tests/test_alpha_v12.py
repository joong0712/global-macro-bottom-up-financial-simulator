"""K-SWING v1.2 no-leakage, bracket-label and deterministic regime tests."""
import numpy as np
import pandas as pd
import pytest

from research.k_swing.alpha_common_v12 import (
    feature_panel, training_bracket_labels, assert_protected_eval_frame,
    TRAIN_LAST, LABEL_MATURITY_LAST,
)
from research.k_swing.alpha_ranker_v12 import rank_from_predictions
from research.k_swing.alpha_regime_v12 import regime_by_date, route_signals


def synthetic_prices():
    dates = pd.bdate_range("2018-01-01", periods=490)
    close = 2200. + np.sin(np.arange(len(dates)) / 6.0) * 20
    bars = pd.DataFrame({
        "date": dates, "ticker": "000123",
        "open": close, "high": close + 30,
        "low": close - 30, "close": close,
        "volume": 3e6, "turnover": 5e9,
        "unsafe_session": False,
    })
    return dates, bars


def test_features_are_asof_and_do_not_react_to_future():
    dates, b = synthetic_prices()
    first = feature_panel(b, dates)
    altered = b.copy()
    altered.loc[altered.index[-1], ["open", "high", "low", "close"]] = [
        2800., 2900., 2700., 2800.]
    second = feature_panel(altered, dates)
    assert not first.empty
    pd.testing.assert_frame_equal(
        first.loc[first.date.lt(dates[-1])].reset_index(drop=True),
        second.loc[second.date.lt(dates[-1])].reset_index(drop=True),
    )


def test_missing_or_unsafe_history_invalidates_candidates():
    dates, b = synthetic_prices()
    assert not feature_panel(b, dates).empty
    b.loc[b.index[-253], "unsafe_session"] = True
    out = feature_panel(b, dates)
    assert not out.date.eq(dates[-1]).any()
    dates, b = synthetic_prices()
    b = b.loc[b.date.ne(dates[-20])]
    out = feature_panel(b, dates)
    assert not out.date.eq(dates[-1]).any()


def test_intraday_stop_first_in_training_label_when_both_hit():
    dates, b = synthetic_prices()
    # 2019 training date at i=330, safe future ten sessions.
    i = 330
    assert dates[i].year == 2019
    b.loc[i + 1, ["open", "high", "low", "close"]] = [2200., 2400., 2100., 2200.]
    cand = pd.DataFrame({"date": [dates[i]], "ticker": ["000123"]})
    out = training_bracket_labels(b, cand, dates, horizon=5)
    assert len(out) == 1
    expected = .97 * (.9975 / 1.0025) - 1
    assert out.iloc[0].net_bracket_label == pytest.approx(expected)


def test_unsafe_held_session_excludes_learning_label():
    dates, b = synthetic_prices()
    i = 330
    b.loc[i + 1, "unsafe_session"] = True
    candidate = pd.DataFrame({"date": [dates[i]], "ticker": ["000123"]})
    assert training_bracket_labels(b, candidate, dates, horizon=10).empty


def test_training_and_late_holdout_locked():
    dates, b = synthetic_prices()
    cand = pd.DataFrame({"date": [pd.Timestamp("2021-02-01")],
                         "ticker": ["000123"]})
    with pytest.raises(ValueError, match="frozen"):
        training_bracket_labels(b, cand, dates, horizon=10)
    with pytest.raises(ValueError, match="locked"):
        feature_panel(b.assign(date=pd.bdate_range("2023-01-02", periods=len(dates))),
                      pd.bdate_range("2023-01-02", periods=len(dates)))
    with pytest.raises(ValueError, match="Evaluation"):
        assert_protected_eval_frame(pd.DataFrame({"date": [pd.Timestamp("2026-01-01")]}))
    assert TRAIN_LAST < LABEL_MATURITY_LAST < pd.Timestamp("2021-01-01")


def test_regime_asof_and_frozen_routes():
    dates = pd.bdate_range("2021-01-01", periods=75)
    rows = []
    for d in dates:
        for ticker in ("000001", "000002", "000003", "000004", "000005",
                       "000006", "000007", "000008", "000009", "000010"):
            rows.append({"date": d, "ticker": ticker, "r1": .0015,
                         "to_ma60": .05})
    panel = pd.DataFrame(rows)
    reg = regime_by_date(panel)
    assert reg.iloc[-1].regime == "bull"
    assert reg.iloc[0].regime == "insufficient_history"
    candidates = pd.DataFrame({
        "date": [dates[-1], dates[-1], dates[-1]],
        "ticker": ["000001", "000002", "000003"],
        "score": [-1., -2., -3.], "turnover": [5e9, 5e9, 5e9],
        "strategy": ["reversal3", "momentum52", "vcr_trend"],
    })
    selected = route_signals(candidates, reg)
    assert selected.ticker.tolist() == ["000002"]
    edited = panel.copy()
    edited.loc[edited.date.eq(dates[-1]), "r1"] = -.5
    updated = regime_by_date(edited)
    pd.testing.assert_frame_equal(reg.iloc[:-1], updated.iloc[:-1])


def test_ml_predictions_only_positive_are_ranked():
    f = pd.DataFrame({
        "date": [pd.Timestamp("2021-01-01")] * 3,
        "ticker": ["000001", "000002", "000003"],
        "turnover": [5e9] * 3,
    })
    out = rank_from_predictions(f, [.015, -.001, .008])
    assert set(out.ticker) == {"000001", "000003"}
    assert out.set_index("ticker").loc["000001", "score"] == -.015
    with pytest.raises(ValueError, match="Non-finite"):
        rank_from_predictions(f, [.2, np.nan, 0])
