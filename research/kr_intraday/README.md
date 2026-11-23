# KR Intraday Research v1

Experimental long-only KOSPI/KOSDAQ day-trading research. No live trading and no claimed returns.

## Input CSV
Required: timestamp (Asia/Seoul ISO string), symbol, open, high, low, close, volume. Optional: sector, spread_bps, halted. One row per 1-minute bar. Bars are labelled by their **start time**. Supply only regular-session 09:00–15:30 observations. Data must be sorted, unique by (timestamp,symbol), with positive prices and nonnegative volume. The engine rejects invalid input. Use historical point-in-time sector membership and include delisted securities in production datasets.

## Execution
```bash
python -m research.kr_intraday.backtest --input /path/to/minutes.csv --output /tmp/kr_intraday_trades.csv
python -m unittest discover -s research/kr_intraday/tests
```

## v1 scope and limitations
- ORB: first 5 minutes high, signal on 1-minute **close** after 09:05, execute at next bar open, no lookahead.
- VWAP: price-volume approximation using typical price (H+L+C)/3, signal when close crosses above VWAP after being below, execute next open.
- Momentum: 5-bar consolidation break after a 10-bar gain, execute next open.
- Exits: fixed stop and 2R target; if both touched in a bar, assume stop first; flatten on first bar starting 15:10 or later. If gaps through a stop, use open if worse.
- Trades use one position per symbol, no overlapping trades per symbol. Costs are parameterized as round-trip percentage. Fixed-size notional per trade, no portfolio-level cash simulation.
- This is a **signal-engine smoke-test**, not a credible performance study yet. No sector ranking, time-of-day relative volume, order-book fills, VI handling, corporate actions, fees by year, survivorship correction, or walk-forward evaluation. These must be added before making any performance claims.
- Never optimize on the final holdout (2025–2026). Compare 2020–2023 training, 2024 validation and 2025–2026 holdout only after realistic data and fills are available.
