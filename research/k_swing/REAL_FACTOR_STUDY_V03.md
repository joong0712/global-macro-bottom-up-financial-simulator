# K-SWING v0.3 — real Korean stock factor experiment

Status: exploratory historical evaluation, NOT an executable investment backtest.

## Fixed protocol (avoid look-ahead)

- Training: 2019–2022 (factor direction and top-five factor selection frozen here).
- Validation: 2023. Test: 2024–2025, held out from factor-selection decision.
- Signal computed at trading-day T close; entry assumed T+1 open; exit T+5/T+10 close.
- Last ten signal sessions of 2022, 2023 and 2025 excluded to prevent horizon labels crossing period boundaries.
- Requires v0.2 screened Parquet-derived data with unsafe_session; source values are not adjusted/certified for all corporate actions.
- Source historical observations go through 2026-11-06 for context, but model evaluation ends 2025.

## Factor calculation and eligible universe

- All 18 pre-existing technical indicators; no formula search/tuning yet.
- Minimum *signal-time* close 1,000 KRW and signal-time turnover 100 million KRW; symbol had to trade on T.
- Entire 5/10-session forward holding window must have nonmissing traded OHLCV and no quarantined event.
- Cross-sectional Rank IC calculated per signal day for factor vs forward return. Fewer than 50 observed eligible stocks? Day/factor excluded.
- Take the ten highest factor values or ten lowest (direction fixed using training Rank IC only).
- Equal-weight benchmark: all eligible names' arithmetic future gross return, not an executable index.
- Gross Top-10 average return and illustrative minus-20-bps roundtrip cost. Overlapping holdings and risk capital are not accounted for.

## Run locally (raw prices stay private)

    python -m pip install -r research/k_swing/requirements.txt
    python -m research.k_swing.marcap_ingest --start-year 2017 --end-year 2026 --keep-raw --output research/k_swing/_local_data
    python -m research.k_swing.quality_audit --data research/k_swing/_local_data
    python -m research.k_swing.factor_real_experiment --data research/k_swing/_local_data --output research/k_swing/_local_data/factor-study

## Publishable outputs

- kswing_factor_results_v03.csv: per factor × horizon × train/validation/test *aggregate* metrics.
- kswing_training_selection_v03.csv: five prespecified factors for each holding horizon, ranked on training data only.
- kswing_research_summary_v03.json: protocol, data quality warnings and run version.

Do not publish raw OHLCV, security-level rankings, daily stock-selection lists or private KIS/DART credentials.
Multiple hypothesis testing, survivorship, instrument types, corporate-action adjustment, security identifier reuse, short-sale restrictions, suspension/delisting fills, market impact and tax regimes are NOT yet resolved. This evaluation must not be described as a trading strategy return or proof of new alpha.

## Reproducibility / data-quality checkpoints

- The KRX-derived marcap source is pinned to commit 94c138df4bf7376be8d28f979edb14020e2a547a.
- The exchange-calendar mismatch must consist only of independently documented 2026-06-03 and 2026-07-17 ad-hoc closures or the experiment refuses to run.
- A positive IC in the training set is not evidence of generalization. Emphasize validation and untouched test separately, with no subsequent tuning on the test result.
