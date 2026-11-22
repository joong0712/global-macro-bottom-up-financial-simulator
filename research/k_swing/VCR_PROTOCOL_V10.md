# K-SWING v1.0 — VCR breakout research (new candidate, not verified alpha)

This experiment continues research/k-swing-v09 without touching main, Streamlit, deployment, or brokerage orders. **Not ready for live money.** It operates only on screened historical 2017–2022 inputs; signals begin in 2019. The 2023 reused study and 2024–2026 material are not opened in this new algorithm's test. The 2026 independent confirmation set stays locked.

## Precommitted T-close rules

- Eligible ordinary-share history is **not officially verified**; initial screening only uses KOSPI/KOSDAQ-derived screened OHLCV. Missing observations, suspected corporate actions (unsafe_session) in the full required lookback block the signal.
- Trading turnover: prior 20 sessions average ≥ KRW 3bn, T-session turnover ≥ KRW 3bn.
- Bollinger width: (4 × population SD20(close) / mean20(close)). Width on **T-1**, ranked against the previous 120-session window ending T-1, must be ≤ its 20th percentile. The breakout candle's width is never used to decide pre-breakout compression.
- Breakout at T close: close(T) > max(high(T-20), ..., high(T-1)). Current day high is excluded.
- Volume at T: >0 and ≥ 1.8 × mean(volume(T-20), ..., volume(T-1)). A 140-session complete clean-bar warmup is required for all comparators.
- Same-universe controls: (a) 20-session close breakout, (b) breakout + volume threshold, (c) VCR = breakout + volume + prior compression. Rank by descending breakout_excess × log1p(volume_ratio) using T-close-only data; ties use ticker code.

## Execution engineering assumptions (NOT verified fills)

- At T close choose up to 10 highest-ranked signals, with **no replacement** after a no-fill; at T+1 opening print buy at most KRW 5m ticket, with cash ≥ required debit and at most 10 simultaneous holdings. Initial cash KRW 100m.
- Stops -3% and takes +8% use actual hypothetical entry-open reference, not T closing price. Hold at most 5 or 10 sessions: exit no later than T+H close.
- Overnight gap beyond a threshold exits using the next available opening print, not the threshold. If one daily bar crosses both stop and take levels, **stop happens first** (conservative unobserved intraday ordering). Price limits and stop orders may prevent these assumed fills.
- Model a **hypothetical** 50-bp roundtrip fee/slippage combined, split equally at entry and exit. No claim of historically correct Korean levy/tax schedules.
- Cash + marked positions are tracked daily. Missing/unsafe held sessions, unresolved exits or suspected stock actions invalidate **all** reported portfolio profit and maximum drawdown. There is no valuation assumption that an untradeable stock can be sold at a convenient close.

## Verification and interpretation

Results are aggregate-only, and share no per-stock prices, orders, or private source data. 2019–2022 have been inspected previously, so **even a strong result here is exploratory**. The three strategy variants and 5/10-session horizons are predeclared; do not optimize on the 2023 reused window. Relative gain from volatility compression and volume must eventually survive an independent matched comparison, corrected corporate actions/delisting universe, no look-ahead, multi-trial statistical controls, and real execution sensitivity. Before any 2026 one-time check, freeze a single final rule/configuration and review the v0.9 Go/No-Go gate.

## Offline private run

From the repository root, with packages installed from research/k_swing/requirements.txt:

1. python -m research.k_swing.marcap_ingest --start-year 2017 --end-year 2022 --keep-raw --output /private/kswing-v10
2. python -m research.k_swing.quality_audit --start-year 2017 --end-year 2022 --data /private/kswing-v10
3. python -m pytest -q research/k_swing/tests/test_vcr_v10.py
4. python -m research.k_swing.vcr_experiment_v10 --data /private/kswing-v10 --output /private/vcr-aggregate --modulus 16

The modulus=16 deterministic sample is **not** representative of a full stock market and is for smoke/engineering tests only. No source OHLCV or ticker-level outputs should be published.
