"""Broad, causal daily-OHLCV indicator research library.

Each value at trading session T is computable using T and earlier observations.
NO back-plotted Chikou span, centered ZigZag, hindsight pivot, or negative shift.
Indicators are individual numerical features, NOT buy/sell signals.
All formula variants and lookback lengths are explicit in FEATURE_CATALOG.
"""
from __future__ import annotations

from dataclasses import dataclass
import numpy as np
import pandas as pd


@dataclass(frozen=True)
class Feature:
    name: str
    family: str
    lookback: int
    description: str


FEATURE_CATALOG: dict[str, Feature] = {}


def _div(a, b):
    return a / b.replace(0, np.nan) if isinstance(b, pd.Series) else a / b


def _ema(s, n):
    return s.ewm(span=n, adjust=False, min_periods=n).mean()


def _wilder(s, n):
    return s.ewm(alpha=1 / n, adjust=False, min_periods=n).mean()


def _mid(h, l, n):
    return (h.rolling(n, min_periods=n).max() + l.rolling(n, min_periods=n).min()) / 2


def _roll(s, n, agg):
    return getattr(s.rolling(n, min_periods=n), agg)()


def compute_indicators(bars: pd.DataFrame) -> pd.DataFrame:
    """Calculate feature panel for ONE ticker, indexed by complete market sessions.

    Missing bars are NOT forward-filled. Suspicious corporate action days from v0.2
    can be supplied in unsafe_session; their effects are excluded by feature lookback.
    """
    required = {"open", "high", "low", "close", "volume", "turnover"}
    if not required.issubset(bars):
        raise ValueError("Missing OHLCV fields: " + str(sorted(required - set(bars))))
    o, h, l, c, v, t = (pd.to_numeric(bars[k], errors="coerce").astype(float)
                         for k in ("open", "high", "low", "close", "volume", "turnover"))
    if not bars.index.is_monotonic_increasing or bars.index.has_duplicates:
        raise ValueError("Bars must have unique, sorted session index")
    if "unsafe_session" in bars:
        raw = bars["unsafe_session"].astype("string").str.lower()
        if raw.dropna().isin(["true", "false", "1", "0"]).all() is False:
            raise ValueError("unsafe_session must be a boolean field")
        risk = raw.isin(["true", "1"]) | raw.isna()
    else:
        risk = pd.Series(False, index=bars.index)
    valid = c.gt(0) & o.gt(0) & h.ge(c) & h.ge(o) & l.le(c) & l.le(o) & l.gt(0) & v.gt(0) & t.gt(0)
    risk = risk | ~valid
    out: dict[str, pd.Series] = {}
    catalog: dict[str, Feature] = {}

    def add(name, value, family, lookback, description=""):
        if name in out:
            raise ValueError(f"Duplicate factor: {name}")
        if not isinstance(value, pd.Series):
            raise TypeError(f"Factor {name} must be a pandas Series")
        # All input-derived indicators must avoid tiny warmup samples.
        series = pd.to_numeric(value.reindex(c.index), errors="coerce").astype(float)
        series = series.replace([np.inf, -np.inf], np.nan)
        contaminated = risk.rolling(int(lookback), min_periods=1).max().astype(bool)
        out[name] = series.where(~contaminated & valid, np.nan)
        catalog[name] = Feature(name, family, int(lookback), description)

    ret = c.pct_change(fill_method=None)
    prev_c = c.shift(1)
    midprice = (h + l) / 2
    typical = (h + l + c) / 3
    hl_range = (h - l).replace(0, np.nan)
    tr = pd.concat([h - l, (h - prev_c).abs(), (l - prev_c).abs()], axis=1).max(axis=1)
    tr = tr.where(prev_c.notna() & h.notna() & l.notna())
    atr14 = _wilder(tr, 14)
    ema12, ema26 = _ema(c, 12), _ema(c, 26)
    rsi_cache = {}

    def rsi(n):
        if n not in rsi_cache:
            delta = c.diff()
            gain = _wilder(delta.clip(lower=0), n)
            loss = _wilder((-delta).clip(lower=0), n)
            rs = _div(gain, loss)
            x = 100 - 100 / (1 + rs)
            x = x.mask(loss.eq(0) & gain.gt(0), 100)
            x = x.mask(loss.eq(0) & gain.eq(0), 50)
            rsi_cache[n] = x
        return rsi_cache[n]

    # Trend, averages, price location
    for n in (5, 10, 20, 50, 100, 200):
        add(f"sma_gap_{n}", _div(c, _roll(c, n, "mean")) - 1,
            "trend", n, "Close / n-session SMA - 1")
        add(f"ema_gap_{n}", _div(c, _ema(c, n)) - 1,
            "trend", max(3 * n, n), "Close / n-session EMA - 1 (warmup may be truncated)")
    weights20 = np.arange(1., 21.)
    wma20 = c.rolling(20, min_periods=20).apply(
        lambda a: float(np.dot(a, weights20) / weights20.sum()), raw=True)
    add("wma_gap_20", _div(c, wma20) - 1, "trend", 20)
    vwma20 = _div((c * v).rolling(20, min_periods=20).sum(),
                  v.rolling(20, min_periods=20).sum())
    add("vwma_gap_20", _div(c, vwma20) - 1, "trend", 20)
    d_ema20 = 2 * _ema(c, 20) - _ema(_ema(c, 20), 20)
    add("dema_gap_20", _div(c, d_ema20) - 1, "trend", 100)
    e1 = _ema(c, 20); e2 = _ema(e1, 20); e3 = _ema(e2, 20)
    tema20 = 3 * e1 - 3 * e2 + e3
    add("tema_gap_20", _div(c, tema20) - 1, "trend", 120)
    add("trima_gap_20", _div(c, _roll(_roll(c, 10, "mean"), 11, "mean")) - 1, "trend", 20)

    macd = ema12 - ema26
    sig = _ema(macd, 9)
    add("macd_pct", _div(macd, c), "trend", 50)
    add("macd_signal_pct", _div(sig, c), "trend", 65)
    add("macd_hist_pct", _div(macd - sig, c), "trend", 65)
    ppo = _div(macd, ema26) * 100
    ppo_signal = _ema(ppo, 9)
    add("ppo", ppo, "trend", 50)
    add("ppo_signal", ppo_signal, "trend", 65)
    add("ppo_hist", ppo - ppo_signal, "trend", 65)
    add("ema_cross_12_26", _div(ema12, ema26) - 1, "trend", 80)

    triple = _ema(_ema(_ema(c, 15), 15), 15)
    add("trix_15", triple.pct_change(fill_method=None) * 100, "trend", 90)
    triple30 = _ema(_ema(_ema(c, 30), 30), 30)
    add("trix_30", triple30.pct_change(fill_method=None) * 100, "trend", 180)

    # Ichimoku: projected spans can be *calculated* at T but the visible cloud at T
    # is formed by calculations from T-26. No Chikou future close is ever used.
    tenkan = _mid(h, l, 9)
    kijun = _mid(h, l, 26)
    span_a_calc = (tenkan + kijun) / 2
    span_b_calc = _mid(h, l, 52)
    cloud_a_t = span_a_calc.shift(26)
    cloud_b_t = span_b_calc.shift(26)
    add("ichi_tenkan_gap", _div(c, tenkan) - 1, "ichimoku", 9)
    add("ichi_kijun_gap", _div(c, kijun) - 1, "ichimoku", 26)
    add("ichi_tenkan_kijun_spread", _div(tenkan, kijun) - 1, "ichimoku", 26)
    add("ichi_cloud_top_gap", _div(c, pd.concat([cloud_a_t, cloud_b_t], axis=1).max(axis=1)) - 1,
        "ichimoku", 78, "Compare current close with cloud *plotted at current time*")
    add("ichi_cloud_bottom_gap", _div(c, pd.concat([cloud_a_t, cloud_b_t], axis=1).min(axis=1)) - 1,
        "ichimoku", 78)
    add("ichi_cloud_thickness", _div(cloud_a_t - cloud_b_t, c), "ichimoku", 78)
    add("ichi_span_a_projected_gap", _div(c, span_a_calc) - 1,
        "ichimoku", 26, "Span A calculable at T, displayed at T+26; not the current cloud")
    add("ichi_span_b_projected_gap", _div(c, span_b_calc) - 1,
        "ichimoku", 52, "Span B calculable at T, displayed at T+26; not the current cloud")
    add("ichi_bullish_cloud", (cloud_a_t > cloud_b_t).where(cloud_a_t.notna() & cloud_b_t.notna()).astype(float),
        "ichimoku", 78)

    # DMI/ADX (Wilder smoothing), vortex, Aroon, price channel
    up_move = h.diff()
    down_move = -l.diff()
    plus_dm = up_move.where((up_move > down_move) & (up_move > 0), 0).where(up_move.notna())
    minus_dm = down_move.where((down_move > up_move) & (down_move > 0), 0).where(down_move.notna())
    di_plus = _div(_wilder(plus_dm, 14), _wilder(tr, 14)) * 100
    di_minus = _div(_wilder(minus_dm, 14), _wilder(tr, 14)) * 100
    dx = _div((di_plus - di_minus).abs(), di_plus + di_minus) * 100
    adx = _wilder(dx, 14)
    add("dmi_plus_14", di_plus, "trend", 40)
    add("dmi_minus_14", di_minus, "trend", 40)
    add("dmi_spread_14", di_plus - di_minus, "trend", 40)
    add("adx_14", adx, "trend", 55)
    add("adxr_14", (adx + adx.shift(14)) / 2, "trend", 70)
    vi_plus = _div((h - l.shift(1)).abs().rolling(14).sum(), tr.rolling(14).sum())
    vi_minus = _div((l - h.shift(1)).abs().rolling(14).sum(), tr.rolling(14).sum())
    add("vortex_plus_14", vi_plus, "trend", 15)
    add("vortex_minus_14", vi_minus, "trend", 15)
    add("vortex_spread_14", vi_plus - vi_minus, "trend", 15)
    def aroon_rank(a):
        return int(np.argmax(a))
    def aroon_low(a):
        return int(np.argmin(a))
    ar_up = h.rolling(25).apply(aroon_rank, raw=True) * 100 / 24
    ar_down = l.rolling(25).apply(aroon_low, raw=True) * 100 / 24
    add("aroon_up_25", ar_up, "trend", 25)
    add("aroon_down_25", ar_down, "trend", 25)
    add("aroon_osc_25", ar_up - ar_down, "trend", 25)

    for n in (20, 55):
        hh = h.shift(1).rolling(n).max()
        ll = l.shift(1).rolling(n).min()
        add(f"donchian_high_gap_{n}", _div(c, hh) - 1, "breakout", n + 1)
        add(f"donchian_low_gap_{n}", _div(c, ll) - 1, "breakout", n + 1)
        add(f"donchian_position_{n}", _div(c - ll, hh - ll), "breakout", n + 1)
        add(f"donchian_width_{n}", _div(hh - ll, c), "breakout", n + 1)
    add("keltner_position_20", _div(c - (_ema(c, 20) - 2 * atr14), 4 * atr14),
        "trend", 65)
    add("keltner_width_20", _div(4 * atr14, c), "volatility", 65)
    add("dpo_causal_20", _div(c - _roll(c, 20, "mean").shift(11), c), "trend", 31,
        "Noncentered: not back-shifted into unavailable history")
    add("choppiness_14", 100 * np.log10(_div(tr.rolling(14).sum(), h.rolling(14).max() - l.rolling(14).min())) / np.log10(14),
        "trend", 15)
    for n in (10, 20):
        add(f"efficiency_ratio_{n}",
            _div((c - c.shift(n)).abs(), c.diff().abs().rolling(n).sum()),
            "trend", n + 1)

    # Momentum and oscillators
    for n in (7, 14, 21, 28):
        add(f"rsi_wilder_{n}", rsi(n), "momentum", n + 1)
    for n in (3, 5, 10, 20, 40, 60, 120):
        add(f"roc_{n}", c.pct_change(n, fill_method=None), "momentum", n + 1)
    for n in (14, 28):
        low = l.rolling(n).min()
        high = h.rolling(n).max()
        stoch = _div(c - low, high - low) * 100
        add(f"stoch_k_{n}", stoch, "momentum", n)
        add(f"stoch_d_{n}", stoch.rolling(3).mean(), "momentum", n + 2)
        add(f"williams_r_{n}", -100 * _div(high - c, high - low), "momentum", n)
    add("stoch_rsi_14", _div(rsi(14) - rsi(14).rolling(14).min(),
                            rsi(14).rolling(14).max() - rsi(14).rolling(14).min()) * 100,
        "momentum", 28)
    add("stoch_rsi_signal_14", _div(rsi(14) - rsi(14).rolling(14).min(),
                            rsi(14).rolling(14).max() - rsi(14).rolling(14).min()).rolling(3).mean() * 100,
        "momentum", 30)
    mfi_typical = typical * v
    tp_change = typical.diff()
    for n in (14, 28):
        pos_money = mfi_typical.where(tp_change > 0, 0).rolling(n).sum()
        neg_money = mfi_typical.where(tp_change < 0, 0).rolling(n).sum()
        money_ratio = _div(pos_money, neg_money)
        mfi = 100 - 100 / (1 + money_ratio)
        mfi = mfi.mask((neg_money == 0) & (pos_money > 0), 100)
        mfi = mfi.mask((neg_money == 0) & (pos_money == 0), 50)
        add(f"mfi_{n}", mfi, "volume", n + 1)
    mean_dev = (typical - typical.rolling(20).mean()).abs().rolling(20).mean()
    add("cci_20", _div(typical - typical.rolling(20).mean(), .015 * mean_dev),
        "momentum", 39)
    add("cmo_14", 100 * _div(c.diff().clip(lower=0).rolling(14).sum() -
                           (-c.diff().clip(upper=0)).rolling(14).sum(),
                           c.diff().abs().rolling(14).sum()),
        "momentum", 15)
    bull = _ema(c.diff().clip(lower=0), 25)
    bear = _ema((-c.diff().clip(upper=0)), 25)
    add("tsi_25_13", 100 * _div(_ema(_ema(c.diff(), 25), 13), _ema(_ema(c.diff().abs(), 25), 13)),
        "momentum", 100)
    add("awesome_5_34", midprice.rolling(5).mean() - midprice.rolling(34).mean(),
        "momentum", 34)
    uo_buy = c - pd.concat([l, prev_c], axis=1).min(axis=1)
    uo_buy = uo_buy.where(prev_c.notna())
    uo = (4 * _div(uo_buy.rolling(7).sum(), tr.rolling(7).sum()) +
          2 * _div(uo_buy.rolling(14).sum(), tr.rolling(14).sum()) +
          _div(uo_buy.rolling(28).sum(), tr.rolling(28).sum())) * (100 / 7)
    add("ultimate_osc_7_14_28", uo, "momentum", 29)
    weighted_roc = 4 * c.pct_change(10, fill_method=None).rolling(10).mean() + \
                   3 * c.pct_change(15, fill_method=None).rolling(10).mean() + \
                   2 * c.pct_change(20, fill_method=None).rolling(10).mean() + \
                   c.pct_change(30, fill_method=None).rolling(15).mean()
    add("kst_osc", weighted_roc, "momentum", 46)
    add("coppock_11_14", (c.pct_change(11, fill_method=None) +
                            c.pct_change(14, fill_method=None)).rolling(10).mean(),
        "momentum", 24)
    add("balance_of_power", _div(c - o, h - l), "momentum", 1)

    # Volatility and risk
    for n in (7, 14, 20):
        add(f"atr_wilder_pct_{n}", _div(_wilder(tr, n), c), "volatility", n * 3)
    for n in (10, 20, 60):
        add(f"realized_vol_{n}", ret.rolling(n).std(ddof=1) * np.sqrt(252),
            "volatility", n + 1)
        add(f"price_zscore_{n}",
            _div(c - c.rolling(n).mean(), c.rolling(n).std(ddof=1)),
            "statistics", n)
    for n in (20, 50):
        avg = c.rolling(n).mean()
        std = c.rolling(n).std(ddof=0)
        add(f"bb_percent_b_{n}", _div(c - (avg - 2 * std), 4 * std),
            "volatility", n)
        add(f"bb_bandwidth_{n}", _div(4 * std, avg), "volatility", n)
    bb20 = c.rolling(20).std(ddof=0) * 4 / c.rolling(20).mean()
    kc20 = _div(4 * atr14, c)
    add("squeeze_bb_keltner", (bb20 < kc20).where(bb20.notna() & kc20.notna()).astype(float),
        "volatility", 65)
    log_hl = np.log(_div(h, l))
    add("parkinson_vol_20", np.sqrt(log_hl.pow(2).rolling(20).mean() * 252 / (4 * np.log(2))),
        "volatility", 20)
    gk_daily = .5 * log_hl.pow(2) - (2 * np.log(2) - 1) * np.log(_div(c, o)).pow(2)
    add("garman_klass_vol_20", np.sqrt(gk_daily.rolling(20).mean().clip(lower=0) * 252),
        "volatility", 20)
    add("daily_true_range_pct", _div(tr, c), "volatility", 2)
    rolling_peak14 = c.rolling(14).max()
    drawdown = (100 * _div(c - rolling_peak14, rolling_peak14)).clip(upper=0)
    add("ulcer_index_14", np.sqrt(drawdown.pow(2).rolling(14).mean()),
        "volatility", 27)
    add("chaikin_vol_10", _ema(h - l, 10).pct_change(10, fill_method=None),
        "volatility", 45)

    # Volume / money flow (daily-OHLCV only; no actual institutional trade records)
    pct_c = ret.replace([np.inf, -np.inf], np.nan)
    flow_sign = np.sign(c.diff()) * v
    obv = flow_sign.fillna(0).cumsum()
    for n in (10, 20):
        add(f"obv_slope_{n}", _div(obv.diff(n), v.rolling(n).sum()), "volume", n + 1)
    for n in (10, 20, 60):
        add(f"relative_volume_{n}", _div(v, v.shift(1).rolling(n).mean()), "volume", n + 1)
        add(f"relative_turnover_{n}", _div(t, t.shift(1).rolling(n).mean()), "volume", n + 1)
    money_mult = (_div((c - l) - (h - c), hl_range)).fillna(0)
    money_volume = money_mult * v
    adl = money_volume.cumsum()
    for n in (10, 20):
        add(f"cmf_{n}", _div(money_volume.rolling(n).sum(), v.rolling(n).sum()),
            "volume", n)
        add(f"adl_flow_{n}", _div(adl.diff(n), v.rolling(n).sum()),
            "volume", n + 1)
    add("chaikin_osc_3_10", _div(_ema(adl, 3) - _ema(adl, 10), v.rolling(20).mean()),
        "volume", 30)
    pvt_inc = pct_c * v
    pvt = pvt_inc.fillna(0).cumsum()
    add("pvt_flow_20", _div(pvt.diff(20), v.rolling(20).sum()), "volume", 21)
    force = c.diff() * v
    add("force_index_13_normalized", _div(_ema(force, 13), t.rolling(20).mean()),
        "volume", 55)
    pvo = 100 * _div(_ema(v, 12) - _ema(v, 26), _ema(v, 26))
    add("pvo_12_26", pvo, "volume", 80)
    add("pvo_hist_12_26_9", pvo - _ema(pvo, 9), "volume", 90)
    for n in (10, 20):
        roll_vwap = _div((typical * v).rolling(n).sum(), v.rolling(n).sum())
        add(f"rolling_typical_vwap_gap_{n}", _div(c, roll_vwap) - 1, "volume", n,
            "OHLCV approximation, NOT actual intraday/anchored VWAP")
    nvi = (1 + ret.where(v.lt(v.shift(1)), 0).fillna(0)).cumprod()
    pvi = (1 + ret.where(v.gt(v.shift(1)), 0).fillna(0)).cumprod()
    add("nvi_20_return", nvi.pct_change(20, fill_method=None), "volume", 21)
    add("pvi_20_return", pvi.pct_change(20, fill_method=None), "volume", 21)
    add("money_flow_balance", _div(money_volume, v), "volume", 1)

    # Support/resistance — levels using past/current prices only, never future swings
    for n in (20, 60):
        hi = h.rolling(n).max()
        lo = l.rolling(n).min()
        for fraction in (.236, .382, .5, .618, .786):
            level = hi - fraction * (hi - lo)
            label = str(fraction).replace(".", "")
            add(f"fibo_{n}_{label}_gap", _div(c, level) - 1,
                "support_resistance", n, "Rolling-window Fibonacci retracement level (not hindsight pivot)")
    pp = (h.shift(1) + l.shift(1) + c.shift(1)) / 3
    add("classic_pivot_gap", _div(c, pp) - 1, "support_resistance", 2)
    add("classic_r1_gap", _div(c, 2 * pp - l.shift(1)) - 1, "support_resistance", 2)
    add("classic_s1_gap", _div(c, 2 * pp - h.shift(1)) - 1, "support_resistance", 2)
    add("camarilla_r3_gap", _div(c, c.shift(1) + 1.1 * (h.shift(1) - l.shift(1)) / 4) - 1,
        "support_resistance", 2)
    add("camarilla_s3_gap", _div(c, c.shift(1) - 1.1 * (h.shift(1) - l.shift(1)) / 4) - 1,
        "support_resistance", 2)

    # Candles: documented purely as heuristics, not TA-Lib pattern recognizers
    body = c - o
    add("candle_body_pct", _div(body, o), "candlestick", 1)
    add("candle_body_range_fraction", _div(body.abs(), hl_range), "candlestick", 1)
    add("candle_lower_wick_fraction", _div(pd.concat([o, c], axis=1).min(axis=1) - l, hl_range),
        "candlestick", 1)
    add("candle_upper_wick_fraction", _div(h - pd.concat([o, c], axis=1).max(axis=1), hl_range),
        "candlestick", 1)
    add("candle_close_location", _div(c - l, hl_range), "candlestick", 1)
    add("candle_doji", (_div(body.abs(), hl_range) < .10).where(hl_range.notna()).astype(float),
        "candlestick", 1)
    add("candle_hammer", ((_div(pd.concat([o, c], axis=1).min(axis=1) - l, hl_range) > .6) &
                          (_div(h - pd.concat([o, c], axis=1).max(axis=1), hl_range) < .15)).where(hl_range.notna()).astype(float),
        "candlestick", 1)
    add("bullish_engulfing_heuristic",
        ((c > o) & (c.shift(1) < o.shift(1)) & (o <= c.shift(1)) & (c >= o.shift(1))).astype(float),
        "candlestick", 2)
    add("bearish_engulfing_heuristic",
        ((c < o) & (c.shift(1) > o.shift(1)) & (o >= c.shift(1)) & (c <= o.shift(1))).astype(float),
        "candlestick", 2)
    add("opening_gap_pct", _div(o, prev_c) - 1, "candlestick", 2)

    # Distribution (do not substitute for beta/sector/foreign flows)
    for n in (20, 60):
        add(f"return_skew_{n}", ret.rolling(n).skew(), "statistics", n + 1)
        add(f"return_kurt_{n}", ret.rolling(n).kurt(), "statistics", n + 1)
    add("linreg_slope_20_pct", _div(c.diff(20), c.shift(20)) / 20,
        "statistics", 21, "Simple 20-day average slope proxy; not least-squares LINEARREG_SLOPE")
    add("rolling_drawdown_20", _div(c, c.rolling(20).max()) - 1, "statistics", 20)
    add("rolling_drawdown_60", _div(c, c.rolling(60).max()) - 1, "statistics", 60)

    # Causal features mask event/warmup within *each feature's* lookback.
    result = pd.DataFrame(out, index=bars.index)
    FEATURE_CATALOG.clear()
    FEATURE_CATALOG.update(catalog)
    return result


def catalog_frame() -> pd.DataFrame:
    """Use after compute_indicators; output definitions and lookbacks."""
    return pd.DataFrame([vars(x) for x in FEATURE_CATALOG.values()]).sort_values(["family", "name"])
