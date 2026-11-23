# Data acquisition and validation requirements

## Minimum files
1. minutes.csv: timestamp (Asia/Seoul naive local), symbol, open, high, low, close, volume. Complete KRX regular-session 1-minute OHLCV, including zero-trade intervals or explicit missing-minute markers.
2. snapshots.csv: timestamp, symbol, sector, close, volume, baseline_turnover, prev_close, spread_bps. Snapshots must be built strictly from data available **by the snapshot timestamp**. baseline_turnover is prior 20 trading days' average cumulative turnover at the same clock time; exclude current day. A snapshot may contain cumulative or per-minute volume, but the current scanner expects **per-minute** volume.
3. Historical security master: point-in-time listing/delisting, common stock flags, historical sector membership, halts, VI, price limits, corporate actions.
4. Trading-cost schedule: commission, transaction tax by effective date/venue, spread and slippage estimates.

## Sourcing
Investigate licensed minute-history from a Korean broker API or market-data vendor; check historical coverage, redistribution rights, and per-symbol limits. Do not assume free KRX daily-data endpoints provide intraday minute history. The repository does not contain a licensed minute dataset.

## Blocking caveats
- Current pipeline uses selection at 09:10 but the strategy engine can generate 09:05–09:09 signals on that selected universe: **this is lookahead**. For valid research, enforce entry signals strictly after selection time or generate earlier point-in-time snapshots. DO NOT interpret current pipeline results as performance until this is fixed.
- Current scanner uses bar close * volume as approximate turnover and does not model venue-specific trades.
- Missing-minute gaps, trading halts, VI, order-book liquidity and delisted stocks remain unhandled.
- Signal-engine stop/target processing is OHLC-only; same-bar sequence unknown.
- Separate training/validation/holdout before parameter tuning; no backtest metrics are reported yet.
