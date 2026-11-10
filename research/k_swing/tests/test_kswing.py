"""Unit checks for look-ahead, entry timing, splits, missing sessions, and CLI."""
import numpy as np
import pandas as pd
import pytest

from research.k_swing.data import validate_prices, load_calendar
from research.k_swing.factors import compute_symbol_factors, FACTOR_NAMES
from research.k_swing.targets import make_symbol_targets, build_panel
from research.k_swing.splits import assign_splits
from research.k_swing.evaluation import run_evaluation


def sample_prices(n=100, tickers=6):
    dates = pd.bdate_range("2024-01-01", periods=n)
    records = []
    for code in range(tickers):
        for i, date in enumerate(dates):
            opening = 100 + code + i * (.11 + code / 300)
            close = opening + np.sin(i / 7 + code) * .5
            records.append((date, f"{code+1:06d}", opening,
                            max(opening, close)+1, min(opening, close)-1,
                            close, 1000+i*3, 1e6+i*5000))
    return validate_prices(pd.DataFrame(records, columns=[
        "date", "ticker", "open", "high", "low", "close", "volume", "turnover"
    ]))


def test_price_validations():
    frame = sample_prices(30, 2)
    assert frame.ticker.iloc[0] == "000001"
    with pytest.raises(ValueError, match="중복"):
        validate_prices(pd.concat([frame, frame.iloc[[0]]]))
    bad = frame.copy()
    bad.loc[0, "high"] = 1
    with pytest.raises(ValueError, match="고가"):
        validate_prices(bad)
    bad = frame.copy()
    bad.loc[0, "volume"] = -1
    with pytest.raises(ValueError, match="음수"):
        validate_prices(bad)


def test_invalid_stock_code_rejected():
    bad = sample_prices(30, 1)
    bad.loc[0, "ticker"] = "abc"
    with pytest.raises(ValueError, match="종목코드"):
        validate_prices(bad)


def test_factors_do_not_look_ahead():
    data = sample_prices(80, 1)
    dates = load_calendar(None, data)
    symbol = data.drop(columns="ticker").set_index("date").reindex(dates)
    original = compute_symbol_factors(symbol)
    changed = symbol.copy()
    changed.loc[dates[65]:, "close"] *= 1.5
    changed.loc[dates[65]:, "high"] = changed.loc[dates[65]:, ["high", "close"]].max(axis=1)
    altered = compute_symbol_factors(changed)
    pd.testing.assert_frame_equal(original.loc[:dates[64]], altered.loc[:dates[64]])
    assert len(FACTOR_NAMES) == 18


def test_target_entry_tplus1_open_exit_tplus5_close():
    dates = pd.bdate_range("2024-01-01", periods=20)
    frame = pd.DataFrame({
        "open": np.arange(100,120,dtype=float),
        "close": np.arange(101,121,dtype=float),
        "high": np.arange(103,123,dtype=float),
        "low": np.arange(99,119,dtype=float),
        "volume": np.ones(20),
    }, index=dates)
    out = make_symbol_targets(frame)
    assert out.loc[dates[0], "forward_return_5"] == pytest.approx(106/101-1)
    assert out.loc[dates[0], "mfe_5"] == pytest.approx(108/101-1)
    assert out.loc[dates[0], "mae_5"] == pytest.approx(100/101-1)
    assert out.loc[dates[0], "entry_date_5"] == dates[1]
    assert out.loc[dates[0], "exit_date_5"] == dates[5]
    assert np.isnan(out.loc[dates[-4], "forward_return_5"])


def test_missing_halted_day_invalidates_label():
    dates = pd.bdate_range("2024-01-01", periods=20)
    frame = pd.DataFrame({
        "open": 100., "close": 102., "high": 104., "low": 99., "volume": 1000.,
    }, index=dates)
    frame.loc[dates[3], ["open", "close", "high", "low", "volume"]] = np.nan
    target = make_symbol_targets(frame)
    assert np.isnan(target.loc[dates[0], "forward_return_5"])
    assert np.isfinite(target.loc[dates[4], "forward_return_5"])


def test_panel_embargo():
    data = sample_prices(120, 7)
    calendar = load_calendar(None, data)
    panel = build_panel(data, calendar)
    assert len(panel) == len(data)
    assert panel["ret_10"].notna().any()
    frame, meta = assign_splits(panel, calendar, embargo_sessions=10)
    assert set(frame["split"].unique()) >= {
        "train", "validation", "test", "embargo_or_incomplete"
    }
    index = pd.Series(range(len(calendar)), index=calendar)
    train_end = calendar.get_loc(pd.Timestamp(meta["train_end"]))
    valid_end = calendar.get_loc(pd.Timestamp(meta["validation_end"]))
    assert (frame.loc[frame.split.eq("train"), "date"].map(index) + 10 <= train_end).all()
    assert (frame.loc[frame.split.eq("validation"), "date"].map(index) + 10 <= valid_end).all()


def test_train_only_factor_direction():
    data = sample_prices(120, 8)
    calendar = load_calendar(None, data)
    panel, _ = assign_splits(build_panel(data, calendar), calendar)
    metrics, ranking = run_evaluation(panel, top_k=2, min_train_ic_days=10)
    assert len(metrics) == len(FACTOR_NAMES) * 2 * 3
    assert len(ranking) == len(FACTOR_NAMES) * 2
    changed = panel.copy()
    mask = changed["split"].isin(["validation", "test"])
    changed.loc[mask, "ret_5"] *= -1
    _, ranking2 = run_evaluation(changed, top_k=2, min_train_ic_days=10)
    pd.testing.assert_series_equal(
        ranking.set_index(["factor", "horizon"])["direction_from_train"].sort_index(),
        ranking2.set_index(["factor", "horizon"])["direction_from_train"].sort_index(),
    )


def test_missing_session_in_full_panel():
    data = sample_prices(40, 2)
    missing = sorted(data.date.unique())[12]
    data = data.loc[~(data.date.eq(missing) & data.ticker.eq("000001"))].copy()
    panel = build_panel(data, load_calendar(None, data))
    row = panel[(panel.ticker=="000001") & (panel.date==sorted(data.date.unique())[8])].iloc[0]
    assert np.isnan(row.forward_return_5)
