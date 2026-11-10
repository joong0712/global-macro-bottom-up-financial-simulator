# K-SWING v0.4 — parallel workstreams and provenance

## Workstreams (independent code, never touch production web)

| Stream | Implemented | Validated | Still required before using for trading |
|---|---|---|---|
| Technical indicators | 170 daily-OHLCV variants + the original 18-feature baseline; Ichimoku, MACD, RSI, ADX, supertrend/PSAR, volatility, money flow, candles, Fibonacci | Synthetic formula tests and 2024/2025 market-data smoke | Full cross-sectional performance, verified split-adjusted prices, multiple-comparison correction |
| Market and sector relative strength | relative_strength.py requires explicitly dated market/sector benchmark closes | Independent formula and no-look-ahead tests | Historical KRX benchmark data and point-in-time sector classifications |
| Foreign/institutional trade flows | external_point_in_time.py as-of joins on publicly available timestamps | Tests reject post-close releases used at today's signal | Authorized per-security investor-class transactions with real as-of publishing time |
| DART fundamentals / ECOS / FRED macro | external_point_in_time.py as-of joins for filings and macro series | Tests verify after-close revisions only appear on next session | Actual historical release logs and revision-vintage time series |
| Broad-factor 2019–23 pilot | Stable ticker-code hash sample, 188 calculated columns, training-selected directions, multiple Top-K diagnostics | Unit tests passed; remote pilot status should be confirmed in Actions | Statistically sound larger coverage, market/sector/size controls, independent holdout |

## Public source provenance (as of 2026-11-11)

- [KRX official Open API service list](https://openapi.krx.co.kr/contents/OPP/INFO/service/OPPINFO004.cmd): KOSPI/KOSDAQ indices and stock market data, stated service data start in 2010; requires separate API access/application.
- [KRX investor-class individual-stock trade data page](https://data.krx.co.kr/contents/MDC/MDI/outerLoader/index.cmd?screenId=MDCSTAT023): regular-session trade breakdown scheduled after 15:45 KST and final including after-hours around 20:00. Thus today's end-of-day 15:30 trading signal CANNOT legally use today's finalized investor flows; they are next-session information.
- [Open DART](https://opendart.fss.or.kr/): filing period-end is not the public release timestamp. Only actual disclosure availability timestamp may enter features.
- [FinanceData/marcap](https://github.com/FinanceData/marcap) source snapshot pinned at 94c138df4bf7376be8d28f979edb14020e2a547a; licensing and raw data redistribution must be verified.

## Known methodological limitations

1. 170 numerical variants are NOT 170 independent strategies; many are collinear parameterizations of the same concept.
2. Technical indicator formula variants may differ from charting packages; verify reference calculations before live trading.
3. 2024–2025 was already inspected in v0.3 for baseline factors and is not an untouched period for post-hoc parameter selection.
4. The 2026 confirmation period is locked; do not tune on its results.
5. The sampled pilot is explicitly exploratory, not representative of the full KOSPI/KOSDAQ ordinary-share universe.
6. Even a consistently positive Rank IC does not establish fillable, risk-adjusted portfolio profitability.

**All changed files are research modules/tests/CI only. Production Streamlit web app and main branch are untouched.**