"""Eighteen transparent backward-looking indicators using data through close T."""
import numpy as np
import pandas as pd

FACTOR_NAMES = (
    "ret_1", "ret_5", "ret_10", "ret_20", "sma_gap_5", "sma_gap_20",
    "ema_gap_12_26", "rsi_14", "atr_pct_14", "bb_width_20",
    "volatility_20", "volume_ratio_20", "turnover_ratio_20", "turnover_z_20",
    "close_location", "upper_wick", "obv_flow_10", "breakout_20",
)


def _div(a: pd.Series, b: pd.Series) -> pd.Series:
    return a.div(b.replace(0, np.nan))


def compute_symbol_factors(ohlcv: pd.DataFrame) -> pd.DataFrame:
    """Input indexed by complete exchange sessions, including NaN for missing bars."""
    f = ohlcv
    c, o, h, l = f["close"], f["open"], f["high"], f["low"]
    v, t = f["volume"], f["turnover"]
    one_ret = c.div(c.shift(1)).sub(1)
    out = pd.DataFrame(index=f.index)
    for d in (1, 5, 10, 20):
        contiguous = c.rolling(d + 1, min_periods=d + 1).count().eq(d + 1)
        out[f"ret_{d}"] = c.div(c.shift(d)).sub(1).where(contiguous)
    for d in (5, 20):
        out[f"sma_gap_{d}"] = c.div(c.rolling(d, min_periods=d).mean()).sub(1)

    ema12 = c.ewm(span=12, adjust=False, min_periods=12).mean()
    ema26 = c.ewm(span=26, adjust=False, min_periods=26).mean()
    out["ema_gap_12_26"] = ema12.div(ema26).sub(1).where(
        c.rolling(26, min_periods=26).count().eq(26)
    )

    changes = c.diff()
    up, down = changes.clip(lower=0), -changes.clip(upper=0)
    up_avg = up.rolling(14, min_periods=14).mean()
    down_avg = down.rolling(14, min_periods=14).mean()
    rs = up_avg.div(down_avg.replace(0, np.nan))
    rsi = 100 - 100 / (1 + rs)
    rsi = rsi.mask(down_avg.eq(0) & up_avg.gt(0), 100)
    rsi = rsi.mask(down_avg.eq(0) & up_avg.eq(0), 50)
    out["rsi_14"] = rsi

    prev_close = c.shift(1)
    tr = pd.concat([h - l, (h - prev_close).abs(), (l - prev_close).abs()], axis=1).max(axis=1)
    tr = tr.where(c.notna() & prev_close.notna() & h.notna() & l.notna())
    out["atr_pct_14"] = _div(tr.rolling(14, min_periods=14).mean(), c)
    ma20 = c.rolling(20, min_periods=20).mean()
    std20 = c.rolling(20, min_periods=20).std(ddof=0)
    out["bb_width_20"] = _div(4 * std20, ma20)
    out["volatility_20"] = one_ret.rolling(20, min_periods=20).std(ddof=1) * np.sqrt(252)

    prev_volume = v.shift(1).rolling(20, min_periods=20).mean()
    prev_turnover = t.shift(1).rolling(20, min_periods=20).mean()
    prev_std = t.shift(1).rolling(20, min_periods=20).std(ddof=1)
    out["volume_ratio_20"] = _div(v, prev_volume)
    out["turnover_ratio_20"] = _div(t, prev_turnover)
    out["turnover_z_20"] = _div(t - prev_turnover, prev_std)

    day_range = h - l
    out["close_location"] = _div(c - l, day_range).where(day_range.gt(0), np.nan)
    out["upper_wick"] = _div(h - pd.concat([o, c], axis=1).max(axis=1), day_range).where(day_range.gt(0), np.nan)
    flow = np.sign(changes) * v
    out["obv_flow_10"] = _div(flow.rolling(10, min_periods=10).sum(), v.rolling(10, min_periods=10).sum())
    out["breakout_20"] = c.div(h.shift(1).rolling(20, min_periods=20).max()).sub(1)
    return out.replace([np.inf, -np.inf], np.nan).where(v.gt(0) & t.gt(0), np.nan)
