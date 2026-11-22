# K-SWING v1.2 — profit-first, leakage-guarded parallel ML / regime research

**No live trading. NO VERIFIED PROFITABLE STRATEGY.** The negative v1.0/v1.1 returns remain the reference, not a guarantee that new algorithms will improve them. No 2023–2026 datasets may be read, trained or tuned.

## Frozen parallel algorithms

### A: alpha_ranker_v12 — LightGBM expected NET bracket-return ranker

- Training labels on 2019–2020 T signals only: simulated T+1 open buy, -3% stop/+8% target (both on same bar = stop first) or T+5/T+10 close, with 50bp hypothetical roundtrip fee deducted. A missing/unsafe holding bar invalidates a label.
- Train T dates end **2020-12-01**, all labels mature by **2020-12-15**, development observations begin **2021-01-01**. No shuffled CV, no 2021/2022 outcomes used to fit the model, no 2023–2026 data at all.
- Features known by T: 1/3/5/10/20/60-day returns, 20-day return volatility, volume/turnover ratios to trailing 20, distance to 20/60-day averages, to *prior* 252-day high, close location within daily range.
- Frozen LightGBM: 120 trees, max 15 leaves, learning rate .04, min child samples 100, L2 10, seed 42. 5/10 day models trained independently. Select predictions of hypothetical **net** return >0 and rank by highest predicted net return. No Optuna tuning on evaluated results.

### B: alpha_regime_v12 — predefined causal market-regime switcher

- State uses the historical sampled eligible stocks' *T-date median daily return* and T-date MA60 breadth; this proxy is not KOSPI.
- Bull if trailing 60-observation compound median return >=+3% and breadth >=55% -> 52-week momentum.
- Bear if trailing 20-observation compound median return <=-4% and breadth <=45% -> 3-day rebound.
- Otherwise sideways -> VCR+trend. If market history fewer than 60 observations or fewer than 10 eligible tickers -> hold cash.
- These rules are predeclared, not chosen after observing 2021–22 returns.

## Both tracks: identical cash / historical research assumptions

- Source: marcap_ingest + quality_audit, 2017–2022 KOSPI/KOSDAQ OHLCV, 1/16 hash ticker sample. **Not a representative full market panel**.
- 253 consecutive safe market bars; T close>=1000 KRW and T turnover / previous 20-session average turnover each >=3bn KRW.
- Already-inspected DEVELOPMENT period 2021-01-01 through 2022-12-15 (not pristine independent holdout).
- Notional 100m KRW initial cash, 5m ticket per position, max 10 positions and top 10 daily signals, T-close information -> T+1 opening print, -3% stop/+8% take, 5/10 day holding, roundtrip 50bp hypothetical fee.
- Compare net account return, max drawdown, trades, unknown held sessions, model counts. Zero trades or merely avoiding market exposure is not sufficient to call a strategy profitable.
- Stop-first OHLC rule is conservative but still cannot verify actual opening auction, limit-up fills or intrabar order sequencing.
- Download data only inside ephemeral GitHub CI runner; upload only aggregate metrics, never source prices or individual trades.
- **Research NO-GO remains** until a verified issuer/delisting/corporate-action mapping, actual costs/taxes, feasible fills and exposure-matched comparisons are completed. True independent confirmation windows remain sealed.

## Next after parallel execution

- Compare both tracks to v1.1 VCR+trend and VCR control on the same developmental dates, report losing tracks unmodified.
- Add official KRX historical security IDs, actions/delisting and time-effective fees/taxes, randomized sample robustness, invested-capital normalized account returns.
- Freeze a single code/data hash before any eventual one-shot independent future-period test. No live orders or PR merge into app/main.

## Academic references

- Gu, Kelly & Xiu (2020), Empirical Asset Pricing via Machine Learning, The Review of Financial Studies: https://doi.org/10.1093/rfs/hhaa009
- López de Prado (2018), Advances in Financial Machine Learning, Chapter 7 — matured, purged / embargoed time series labels. Our chronological cut is more basic and not full purged-CV.
- George & Hwang (2004), The 52-Week High and Momentum Investing: https://doi.org/10.1111/j.1540-6261.2004.00695.x
- Jegadeesh (1990), Evidence of Predictable Behavior of Security Returns: https://doi.org/10.1111/j.1540-6261.1990.tb05110.x

Paper results are hypotheses and do NOT establish profitable 5–10-day South Korean stock trades.
