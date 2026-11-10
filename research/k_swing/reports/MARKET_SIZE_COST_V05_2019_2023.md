# K-SWING v0.5 — observed market/size and cost-stress results

## Run provenance

- Real GitHub Actions run **completed successfully**: https://github.com/joong0712/global-macro-bottom-up-financial-simulator/actions/runs/42874818029
- Artifact (aggregate data only): https://github.com/joong0712/global-macro-bottom-up-financial-simulator/actions/runs/42874818029/artifacts/13792630272
- Source: FinanceData/marcap pinned commit `94c138df4bf7376be8d28f979edb14020e2a547a`, 2017–2023 for source/warmup.
- Deterministic ticker-code-hash sample: **328 codes**, **274,055 signal ticker-days**.
- 5 precommitted low-volatility factors and 2 holding horizons; **36,390 daily cost/control diagnostic rows**.
- 2019–2022 training; 2023 **reused exploratory** validation (not new untouched OOS); 2024–2025 not reopened; **2026 confirmation remains unopened**.
- Missing day-security market-cap metadata excluded: 0 rows in this run.

## What size/market adjustment changes

At every T, group eligible tickers by **KOSPI/KOSDAQ × within-market capitalization tercile**. Within each sufficiently sized group (at least 8 stocks), rank indicator and forward 5/10-session return, then compute the pooled correlation. For comparability, **reported IC below is sign-oriented** so a positive figure means *lower volatility was associated with higher subsequent return ranks*. Raw code-level IC before sign orientation is negative.

### 2023, 10-session return: IC persists after market/size adjustment

| Training-selected factor (all low preferred) | Unadjusted oriented Rank IC | Market/size-controlled oriented Rank IC | 2023 days |
|---|---:|---:|---:|
| ATR 14d, original | +0.0979 | +0.0815 | 235 |
| Wilder ATR 7d | +0.1058 | +0.0894 | 235 |
| Garman–Klass vol 20d | +0.1086 | +0.0932 | 235 |
| Parkinson vol 20d | +0.1087 | +0.0936 | 235 |
| Realized vol 60d | +0.1073 | +0.0948 | 235 |

Interpretation: cross-sectional low-volatility rank association decreases in magnitude for most measures after these two controls but remains positive. This is NOT a market-and-size-neutral investable portfolio nor a test of causal effect. Independent sector, time-varying listings, dividends/adjustments and risk premia still matter.

## T+1-open → T+10-close hypothetical signal cohorts

For K=10 lowest-volatility stock selections per signal day, fixed on T:

| Factor | T+1→T+10 mean gross return | Less hypothetical 20 bps | Less hypothetical 50 bps | Less hypothetical 100 bps | 5m KRW order capacity screen pass |
|---|---:|---:|---:|---:|---:|
| Original ATR14 | +0.395% | +0.195% | -0.105% | -0.605% | 32.4% |
| Wilder ATR7 | +0.410% | +0.210% | -0.090% | -0.590% | 32.5% |
| Garman–Klass20 | +0.429% | +0.229% | -0.071% | -0.571% | 38.4% |
| Parkinson20 | +0.425% | +0.225% | -0.075% | -0.575% | 36.2% |
| Realized vol60 | +0.429% | +0.229% | -0.071% | -0.571% | 20.6% |

**Warning:** These are descriptive average **overlapping future-return labels**, not annual returns, cumulative returns or capital-managed backtested profit. A positive mean gross return does not imply outperformance of the eligible-stock benchmark. In the earlier v0.4 2023 pilot, none of the five 10-day Top-10 cohorts had positive average **gross excess return** versus the eligible-universe benchmark.

### The liquidity-screen warning is material

Capacity diagnostic: ticket **KRW 5 million** is at most **0.5% of known signal-date T turnover** (requires signal-day turnover >= KRW 1 billion). Only 20.6–38.4% of daily Top-10 picks across the five indicators pass this hypothetical participation threshold; it is not a next-session order fill calculation. Unknown next-day fills/price limits and close-auction execution remain unverified.

### Top-K sensitivity caution

For K=3 and Parkinson20, 2023 ten-session average gross was **+1.026%**; illustrative minus 100 bps yields +0.026%; for Garman–Klass20 the corresponding figures were +1.077% and +0.077%. But picking K=3 now because it looks better is **ex post optimization** on already-inspected 2023 and cannot validate an independent strategy. Capacity passes were only 40.3% and 44.3% respectively; execution risk remains.

## Methodological shortcomings and next research gates

1. Capitalization on T is from `marcap` and not yet independently crosschecked with KRX's point-in-time issuer references. No reliable 2019–23 historical industry classifications were supplied; **sector neutrality was not tested**.
2. KRX/KIND official rights/split/delisting and issuer identity records require verification; marcap adjusted prices are not certified.
3. The order-capacity test uses T turnover only; actual entry (T+1 opening auction), exit (T+H close), price limits, tax schedules and execution slippage are not modeled.
4. No portfolio return, risk-adjusted Sharpe, path drawdown, turnover, concurrent-position/cash constraints, multiple-testing correction, calendar regime stability or survivorship-free ordinary-share universe.
5. Never infer independent alpha from five correlated volatility indicators. This report is **exploratory**, not investment advice.

## Proposed next phases

- v0.6: KRX/KIND official historical security universe, actual corporate actions, sectors and buyer-class flow with timestamp-proven release/vintages.
- v0.7: Fixed-rule self-financing portfolio execution simulator with real historical taxes and broker fees, open/close auction fills, cash/overlap/risk limits and walk-forward stability.
- v0.8: AI symbolic/evolutionary factor searches strictly on in-sample/training windows, duplicate pruning, FDR multiple-comparison control, strict point-in-time dependencies.
- v0.9: preregister a single finalist rule and inspect untouched 2026 confirmation set once; if valid, paper trade before funding.

**Existing Streamlit website and main branch remained untouched, and no ticker-level/price-level data were uploaded to public GitHub.**