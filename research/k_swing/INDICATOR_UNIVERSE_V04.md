# K-SWING v0.4 — broad technical indicator universe

## Objective

Expand the original 18 indicator variables with a substantially larger, fully **causal** daily-OHLCV universe. This is an indicator library, not an actual factor profitability claim.

Implemented families: Ichimoku Kinko Hyo (tenkan/kijun, current cloud, projected spans), moving averages (SMA/EMA/WMA/DEMA/TEMA/TRIMA/VWMA), MACD, PPO/PVO, TRIX, ADX/DMI/ADXR, Vortex, Aroon, Donchian, Keltner, momentum/ROC, Wilder RSI, Stochastic, StochRSI, Williams %R, MFI, CCI, CMO, TSI, Awesome Oscillator, Ultimate Oscillator, KST, Coppock, ATR, Bollinger, squeeze, Parkinson, Garman-Klass, volume/turnover relative strength, OBV, CMF, Chaikin ADL/Oscillator, PVT, Force Index, negative/positive volume index, rolling daily-typical-price VWAP proxy, Fibonacci rolling retracements, pivot levels, candlestick heuristics, skew/kurtosis and drawdown.

### Critical Ichimoku leak warning

The plotted **current** Senkou A/B cloud is calculated from the relevant moving-price midpoint **26 sessions in the past**. Today's newly computed A/B will be *drawn* 26 bars ahead, but today we know the computed number already; it is not today's plotted cloud. Never use the Chikou Span (`close.shift(-26)`) as a past signal. No negative shift, centered pivot, hindsight ZigZag or future-looking market-event label is present.

### Data availability

Only indicators computable from DAILY open/high/low/close/volume/turnover are included. Institutional/foreign buyer flows, short interest, tick-by-tick VWAP, order book, index/sector relative strength and fundamentals require distinct timestamped source datasets; they must **not** be fabricated from OHLCV.

### Notes on methodology

- Feature names and descriptions are in the built-in FEATURE_CATALOG after a calculation.
- Daily-indicator methods follow transparent pandas-based definitions; differences from TA-Lib chart defaults are possible (RSI uses Wilder-style exponential averages).
- `rolling_typical_vwap_gap_*` is an approximation from daily OHLCV rather than intraday/anchored VWAP.
- Candlestick patterns are simple deterministic heuristics, not exact proprietary pattern-recognition signals.
- Correlated parameter variants do not represent independent discoveries.
- All features are computed using T and earlier only. No data leakage from future shifted visualizations.
- Suspicious v0.2 corporate-action days and invalid bars quarantine each feature for its named backward lookback window.

### Example

```python
from research.k_swing.indicators_expanded import compute_indicators, catalog_frame
expanded = compute_indicators(ohlcv_one_ticker_aligned_to_sessions)
catalog = catalog_frame()
print(expanded.shape, catalog.groupby('family').size())
```

### Next work

1. Test formulas against independent reference calculations and real-split examples.
2. Benchmark memory / throughput on thousands of actual historical tickers.
3. Freeze feature universe and training-selected directions. Run holdout tests **only after** precommitment; old 2024–2025 results are already inspected.
4. Apply factor correlation clustering, FDR/multiple-hypothesis safeguards and time-block bootstrap.
5. Separate relative strength/index, KRX participant flow and point-in-time DART fundamentals into different input adapters.

Reference catalogs: https://ta-lib.org/functions/ and https://github.com/xgboosted/pandas-ta-classic/blob/main/docs/indicators.rst
