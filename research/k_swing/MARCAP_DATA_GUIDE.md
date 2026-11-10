# K-SWING historical market data acquisition (research only)

## Source and scope
- FinanceData/marcap (KRX-derived daily listing data): https://github.com/FinanceData/marcap
- 2017–2026 yearly Parquet files inspected via GitHub, about 19–25 MB each.
- Default pinned commit: 94c138df4bf7376be8d28f979edb14020e2a547a
- KRX official Open API alternative: https://openapi.krx.co.kr/contents/OPP/INFO/service/OPPINFO004.cmd (requires your API key/service approval).

## Private acquisition
From repository root (never modify the Streamlit website):
~~~sh
python -m pip install -r research/k_swing/requirements.txt
python -m pytest -q research/k_swing/tests
python -m research.k_swing.marcap_ingest --start-year 2017 --end-year 2026 --output ./research/k_swing/_local_data
~~~

Data is saved ONLY to gitignored local files:
- _local_data/_private/kswing_prices_YYYY.csv.gz: date,ticker,open,high,low,close,volume,turnover
- _local_data/_private/krx_observed_sessions.csv: provisional observed market calendar
- _local_data/marcap_audit_summary.json: source SHA256 and per-year aggregated QA metrics

These CSV.gz files are accepted by the existing CLI for exploratory *year-at-a-time* analysis. For robust multi-year analysis, combine annual files with warm-up sessions and check all exchange holidays rather than treating each year independently.

## Critical caveats
Market filter alone does not reliably exclude preferred shares, SPACs and every special instrument.
Underlying source prices are not verified as corporate-action adjusted. Mergers, splits, suspensions and delisted tickers require explicit reference-data checks.
Market dates observed across stocks are not a verified official exchange session calendar.
Zero-volume dates are preserved, not forward-filled, so untradable time windows may be invalidated downstream.
Before using for real money: confirm point-in-time exchange/issuer information, survivorship-free coverage, real order-fill constraints, settlement, taxes and all redistribution terms.
Do not publish or upload raw OHLCV data to public GitHub repositories, public Actions artifacts or PRs without the necessary permissions.

## GitHub Actions audit
The optional branch-only workflow downloads all years to an ephemeral runner, executes unit tests, and uploads **aggregated quality-control JSON only**. Raw and normalized market data stay private to the runner and are deleted when it exits. Download to your own authorized machine for persistent research.
