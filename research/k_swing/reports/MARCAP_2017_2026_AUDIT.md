# K-SWING historical data acquisition audit (2017–2026)

Actual market-derived yearly files were downloaded and normalized by [GitHub Actions run #42854566791](https://github.com/joong0712/global-macro-bottom-up-financial-simulator/actions/runs/42854566791).

- Upstream: [FinanceData/marcap](https://github.com/FinanceData/marcap) (KRX-derived)
- Upstream pinned commit: `94c138df4bf7376be8d28f979edb14020e2a547a`
- Normalized observations: **5,639,753** across **2,413 observed trading dates**
- Excluded invalid security codes: **55,955** market observations
- Excluded missing/bad OHLCV or nonconforming prices: **196,100** market observations
- Date coverage: **2017-01-02 to 2026-11-06** (snapshot, not live as of 2026-11-11)
- GitHub Actions unit tests: **13 passed**

| Year | Normalized OHLCV rows | Distinct codes | Market dates | Invalid-code rows | Bad/incomplete rows |
|---|---:|---:|---:|---:|---:|
| 2017 | 504,738 | 2,191 | 243 | 1,676 | 9,279 |
| 2018 | 519,427 | 2,251 | 244 | 2,396 | 9,176 |
| 2019 | 536,616 | 2,306 | 246 | 3,009 | 15,662 |
| 2020 | 553,351 | 2,377 | 248 | 4,437 | 22,464 |
| 2021 | 574,137 | 2,446 | 248 | 5,116 | 24,541 |
| 2022 | 589,668 | 2,545 | 246 | 5,580 | 21,030 |
| 2023 | 599,244 | 2,600 | 245 | 6,001 | 20,177 |
| 2024 | 615,242 | 2,687 | 244 | 5,856 | 24,613 |
| 2025 | 623,895 | 2,713 | 242 | 7,190 | 24,668 |
| 2026 | 523,435 | 2,683 | 207 | 14,694 | 24,490 |

## Where the data lives

**Raw and normalized securities prices were stored only on the GitHub Actions runner while it executed.**
No prices have been committed to this public repository, and the [run artifact](https://github.com/joong0712/global-macro-bottom-up-financial-simulator/actions/runs/42854566791/artifacts/13782531617) contains **aggregate QA metrics only** (including checksums).
To retain your own permitted local copy, run the documented standalone [ingestion CLI](../marcap_ingest.py):

~~~sh
python -m pip install -r research/k_swing/requirements.txt
python -m research.k_swing.marcap_ingest --start-year 2017 --end-year 2026 --output ./research/k_swing/_local_data
~~~

## Known limitations before any investment research

- Coverage of delisted/common shares and exclusion of preferred shares, SPACs, and other special securities is **not yet verified**.
- Corporate-action price adjustment, splits and mergers, market calendar, and information publication timing require additional verification.
- Excluded price/volume rows may represent suspended/untradable instruments; never forward-fill and treat them as tradable prices.
- This is a **data-acquisition QA**, not a backtest or proof of predictive alpha.
- Respect upstream and KRX licensing; raw securities data redistribution is not authorized by this report.
