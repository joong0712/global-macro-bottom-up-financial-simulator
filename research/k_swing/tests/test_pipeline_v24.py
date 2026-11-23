import numpy as np
import pandas as pd
import pytest

from research.k_swing.pipeline import backtest, config, panel as P, signals, stats


def raw_frame(prices: dict[str, list[float]], start="2021-01-04", changes=None, volume=None,
              opens=None, dept=None, names=None):
    """Marcap-shaped long frame; Changes defaults to close - previous close."""
    dates = pd.bdate_range(start, periods=len(next(iter(prices.values()))))
    rows = []
    for code, closes in prices.items():
        for i, (d, c) in enumerate(zip(dates, closes)):
            if c is None:
                continue
            prev = closes[i - 1] if i and closes[i - 1] is not None else c
            ch = (changes or {}).get((code, i), c - prev)
            vol = (volume or {}).get((code, i), 1_000_000)
            op = (opens or {}).get((code, i), c)
            rows.append({"Date": d, "Code": code, "Name": (names or {}).get(code, f"N{code}"), "Market": "KOSPI",
                         "Dept": (dept or {}).get(code), "Open": op if vol else 0.0, "High": max(op, c) if vol else 0.0,
                         "Low": min(op, c) if vol else 0.0, "Close": c, "Changes": ch, "Volume": vol,
                         "Amount": vol * c})
    return pd.DataFrame(rows)


def test_split_is_adjusted_from_krx_base_price():
    closes = [10000, 10000, 5000, 5100]
    raw = raw_frame({"000010": closes}, changes={("000010", 2): 0.0})  # base = 5000 = half of prior close
    pnl = P.build_panel(raw)
    assert pnl.factor["000010"].iloc[2] == pytest.approx(0.5)
    adj = pnl.adj_close["000010"].tolist()
    assert adj == pytest.approx([5000, 5000, 5000, 5100])


def test_small_bonus_issue_missed_by_old_35pct_screen_is_caught():
    # 0.2 bonus shares per share: price base drops to 1/1.2 (-16.7%), below the old 35% screen.
    closes = [12000, 12000, 10100]
    raw = raw_frame({"000020": closes}, changes={("000020", 2): 100.0})
    pnl = P.build_panel(raw)
    assert pnl.factor["000020"].iloc[2] == pytest.approx(10000 / 12000)
    assert pnl.adj_close["000020"].iloc[2] / pnl.adj_close["000020"].iloc[1] - 1 == pytest.approx(0.01)


def test_holdout_year_is_rejected(tmp_path):
    raw = raw_frame({"000010": [1000, 1001]}, start="2025-12-31")
    path = tmp_path / "x.parquet"
    raw.to_parquet(path)
    with pytest.raises(ValueError, match="2026"):
        P.read_marcap([path])


def test_static_filter_excludes_preferred_spac_reit():
    raw = raw_frame({"000010": [1, 1], "000015": [1, 1], "000020": [1, 1], "000030": [1, 1]},
                    dept={"000020": "SPAC(소속부없음)"}, names={"000030": "테스트리츠"})
    ok = P.static_filter(raw).groupby(raw["Code"]).all()
    assert ok.to_dict() == {"000010": True, "000015": False, "000020": False, "000030": False}


def _random_panel(seed=0, n_days=320, n_codes=6):
    rng = np.random.default_rng(seed)
    prices = {}
    for j in range(n_codes):
        path = 20000 * np.exp(np.cumsum(rng.normal(0, 0.02, n_days)))
        prices[f"{j + 1:05d}0"] = [float(round(x)) for x in path]
    return raw_frame(prices)


def test_scores_and_universe_ignore_future_data():
    raw = _random_panel()
    pnl = P.build_panel(raw)
    cut = pnl.sessions[280]
    changed = raw.copy()
    after = changed["Date"] > cut
    changed.loc[after, ["Open", "High", "Low", "Close"]] *= 3.0
    changed.loc[after, "Changes"] = 0.0
    pnl2 = P.build_panel(changed)
    s = config.PRIMARY.with_(min_turnover=0)
    u1, u2 = P.universe(pnl, s), P.universe(pnl2, s)
    assert u1.loc[:cut].equals(u2.loc[:cut])
    for name, fn in signals.SCORES.items():
        a, b = fn(pnl).loc[:cut], fn(pnl2).loc[:cut]
        # Backward adjustment rescales history uniformly; ratio-based scores must be identical.
        pd.testing.assert_frame_equal(a, b, check_exact=False, rtol=1e-9, obj=name)


def _one_stock_panel(closes, **kwargs):
    return P.build_panel(raw_frame({"000010": closes}, **kwargs))


def _run(pnl, horizon, picks_on, settings=None):
    settings = settings or config.PRIMARY.with_(top_n=1, min_turnover=0, min_history=0)
    eligible = pd.DataFrame(True, index=pnl.sessions, columns=pnl.close.columns)
    picks = {pnl.sessions[i]: ["000010"] for i in picks_on}
    turnover = pd.DataFrame(20e9, index=pnl.sessions, columns=pnl.close.columns)
    start, end = pnl.sessions[min(picks_on)], pnl.sessions[max(picks_on)]
    return backtest.run(pnl, picks, horizon, str(start.date()), str(end.date()), eligible, turnover, settings)


def test_trade_return_uses_next_open_and_planned_close_with_costs():
    closes = [10000, 10000, 10500, 11000, 11500, 12000]
    pnl = _one_stock_panel(closes, opens={("000010", 1): 10000})
    res = _run(pnl, horizon=2, picks_on=[0])
    t = res.trades.iloc[0]
    assert t["entry_date"] == pnl.sessions[1] and t["exit_date"] == pnl.sessions[2]
    assert t["gross_return"] == pytest.approx(10500 / 10000 - 1)
    slip, comm, tax = 0.0010, config.COMMISSION, config.sell_tax(pnl.sessions[2])
    expected = 10500 * (1 - slip) * (1 - comm - tax) / (10000 * (1 + slip) * (1 + comm)) - 1
    assert t["net_return"] == pytest.approx(expected)


def test_limit_up_open_blocks_entry():
    closes = [10000, 12900, 13000, 13000]
    pnl = _one_stock_panel(closes, opens={("000010", 1): 12990})
    res = _run(pnl, horizon=1, picks_on=[0])
    assert res.counters["blocked_entry"] == 1 and res.trades.empty


def test_halted_exit_is_delayed_not_dropped():
    closes = [10000, 10000, 9000, 9000, 8000, 8000]
    pnl = _one_stock_panel(closes, volume={("000010", 2): 0, ("000010", 3): 0})
    res = _run(pnl, horizon=2, picks_on=[0, 1, 2, 3])
    t = res.trades.iloc[0]
    assert t["exit_reason"] == "delayed" and t["exit_date"] == pnl.sessions[4]
    assert t["gross_return"] == pytest.approx(8000 / 10000 - 1)


def test_delisting_exits_at_last_close_with_the_loss():
    closes = [10000, 10000, 3000, None, None, None]
    pnl = P.build_panel(raw_frame({"000010": closes, "000020": [1000] * 6}))
    res = _run(pnl, horizon=3, picks_on=[0])
    t = res.trades.iloc[0]
    assert t["exit_reason"] == "delisted" and t["gross_return"] == pytest.approx(-0.7)


def test_sell_tax_schedule_boundaries():
    assert config.sell_tax(pd.Timestamp("2019-05-29")) == 0.0030
    assert config.sell_tax(pd.Timestamp("2019-05-30")) == 0.0025
    assert config.sell_tax(pd.Timestamp("2022-12-29")) == 0.0023
    assert config.sell_tax(pd.Timestamp("2025-06-30")) == 0.0015


def test_holm_step_down():
    out = stats.holm({"a": 0.01, "b": 0.02, "c": 0.04})
    assert out["a"]["p_holm"] == pytest.approx(0.03) and out["a"]["reject"]
    assert out["b"]["p_holm"] == pytest.approx(0.04) and out["b"]["reject"]
    assert out["c"]["p_holm"] == pytest.approx(0.04) and out["c"]["reject"]
    out = stats.holm({"a": 0.01, "b": 0.04, "c": 0.04})
    assert not out["b"]["reject"] and not out["c"]["reject"]


def test_bootstrap_detects_positive_mean_and_not_zero_mean():
    rng = np.random.default_rng(1)
    assert stats.block_bootstrap_p(rng.normal(0.003, 0.01, 1000))[0] < 0.01
    p_null = stats.block_bootstrap_p(rng.normal(0.0, 0.01, 1000) - 0.0)[0]
    assert p_null > 0.05


def test_long_halt_is_force_closed_at_window_end_not_carried_for_years():
    closes = [10000, 10000, 9000] + [9000] * 30
    vol = {("000010", i): 0 for i in range(2, 33)}
    pnl = _one_stock_panel(closes, volume=vol)
    res = _run(pnl, horizon=2, picks_on=[0])
    assert res.counters["forced_window_end_exit"] == 1
    assert len(res.daily) <= 3


def test_zero_cost_diagnostic_matches_gross_return():
    closes = [10000, 10000, 10500, 11000]
    pnl = _one_stock_panel(closes)
    res = _run(pnl, horizon=2, picks_on=[0],
               settings=config.PRIMARY.with_(top_n=1, min_turnover=0, min_history=0, zero_cost=True))
    t = res.trades.iloc[0]
    assert t["net_return"] == pytest.approx(t["gross_return"])


# ---------------- v25 rank-buffer engine ----------------
from research.k_swing.pipeline import buffer as B, run_v25


def _three_stock_panel(closes=None, opens=None):
    closes = closes or {"000010": [10000, 10100, 10200, 10300, 10400],
                        "000020": [20000, 20000, 20000, 20000, 20000],
                        "000030": [5000, 5000, 5000, 5000, 5000]}
    return P.build_panel(raw_frame(closes, opens=opens))


def _buffer(pnl, score_rows, mode="close", top_n=1, k=2, zero_cost=False):
    score = pd.DataFrame(score_rows, index=pnl.sessions[:len(score_rows)], columns=pnl.close.columns)
    score = score.reindex(pnl.sessions)
    elig = pd.DataFrame(True, index=pnl.sessions, columns=pnl.close.columns)
    tov = pd.DataFrame(20e9, index=pnl.sessions, columns=pnl.close.columns)
    end = pnl.sessions[len(score_rows) - 1]
    return B.run_buffer(pnl, score, elig, tov, str(pnl.sessions[0].date()), str(end.date()),
                        mode=mode, zero_cost=zero_cost, top_n=top_n, buffer_k=k)


def test_buffer_buys_at_signal_close_and_holds_inside_buffer():
    pnl = _three_stock_panel()
    rows = [[3, 2, 1], [2, 3, 1], [1, 3, 2]]  # A best, then rank 2 (kept, K=2), then rank 3 (sold)
    res = _buffer(pnl, rows, zero_cost=True)
    t = res.trades.iloc[0]
    assert t["code"] == "000010" and t["entry_date"] == pnl.sessions[0] and t["exit_date"] == pnl.sessions[2]
    assert t["gross_return"] == pytest.approx(10200 / 10000 - 1)
    assert res.counters["buys"] == 2  # A on day 0, B on day 2


def test_buffer_close_fill_costs():
    pnl = _three_stock_panel()
    res = _buffer(pnl, [[3, 2, 1], [1, 3, 2]])
    t = res.trades.iloc[0]
    slip, tax = 0.0010, config.sell_tax(pnl.sessions[1])
    expected = 10100 * (1 - slip) * (1 - config.COMMISSION - tax) / (10000 * (1 + slip) * (1 + config.COMMISSION)) - 1
    assert t["net_return"] == pytest.approx(expected)


def test_buffer_limit_up_close_blocks_buy():
    closes = {"000010": [10000, 12990, 13000], "000020": [20000, 20000, 20000]}
    pnl = P.build_panel(raw_frame(closes))
    res = _buffer(pnl, [[np.nan, np.nan], [2, 1]], top_n=1, k=1)
    assert res.counters["blocked_buy"] == 1 and res.counters["buys"] == 0


def test_buffer_next_open_mode_fills_at_next_open():
    pnl = _three_stock_panel(opens={("000010", 1): 10050})
    res = _buffer(pnl, [[3, 2, 1], [3, 2, 1], [1, 3, 2]], mode="next_open", zero_cost=True)
    t = res.trades.iloc[0]
    assert t["entry_date"] == pnl.sessions[1] and t["exit_date"] == pnl.sessions[3]
    assert t["gross_return"] == pytest.approx(10300 / 10050 - 1)


def test_v25_holdout_requires_explicit_approval(tmp_path, monkeypatch):
    monkeypatch.delenv("KSWING_OPEN_2026_HOLDOUT", raising=False)
    with pytest.raises(SystemExit, match="locked"):
        run_v25.main(["--marcap-dir", str(tmp_path), "--public-output", str(tmp_path / "o"), "--open-2026-holdout"])


def test_v25_holdout_refuses_second_look(tmp_path, monkeypatch):
    monkeypatch.setenv("KSWING_OPEN_2026_HOLDOUT", run_v25.HOLDOUT_TOKEN)
    pre = tmp_path / "pre.json"
    pre.write_text('{"passed": ["V25A"]}')
    out = tmp_path / "o"
    out.mkdir()
    (out / "HOLDOUT_2026_OPENED").write_text("opened")
    with pytest.raises(SystemExit, match="already opened"):
        run_v25.main(["--marcap-dir", str(tmp_path), "--public-output", str(out), "--open-2026-holdout",
                      "--precheck-json", str(pre)])
