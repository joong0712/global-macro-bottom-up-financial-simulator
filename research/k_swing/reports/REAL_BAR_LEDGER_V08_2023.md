# K-SWING v0.8 — Provisional real-bar cash ledger: 2023

## Source, run and reproducibility

- [GitHub Actions v0.8 parallel run #42894438518](https://github.com/joong0712/global-macro-bottom-up-financial-simulator/actions/runs/42894438518): actual historical cash/volume stress job succeeded.
- [Historical simulator aggregate artifact](https://github.com/joong0712/global-macro-bottom-up-financial-simulator/actions/runs/42894438518/artifacts/13799508262) available for short retention.
- Input: FinanceData/marcap pinned 2017–2023 screened snapshot; SHA-256 deterministic code subsample, **176 distinct ticker codes**, 245 candidate signal sessions in already-inspected year 2023.
- Real observed price *prints*, not verified exchange auction fills, corrected corporate-action data or real broker portfolio reports.
- Frozen signal definitions: select the **lowest** daily `ta__atr_wilder_pct_7` or `ta__parkinson_vol_20` after filtering T price≥KRW1000 and T turnover≥KRW100m; ticket size KRW5m with additional T-day turnover cap of 0.5%.
- Trading: T close scoring, **T+1 opening** hypothetical fill, T+5/T+10 **closing** hypothetical fill. KRW100m initial cash, 10 max concurrent positions. Higher-scored options never substitute hindsight for unfillable top-ranked choices.
- Fixed 32 precommitted scenarios: 2 indicators × H=5/10 × K=3/10 × 20/50/100/200 bps assumed *roundtrip* cost.

## 2023 10-session Top-10 (total assumed cash return on KRW100m, not independent confirmation)

| Factor | Assumed roundtrip 20bps | 50bps | 100bps | 200bps | Hypothetical completed trades | Filtered out on signal-day liquidity |
|---|---:|---:|---:|---:|---:|---:|
| Low Wilder ATR 7d | +4.37% | +2.70% | -0.08% | -5.63% | 111 | 1847 |
| Low Parkinson vol 20d | +5.07% | +3.38% | +0.55% | -5.10% | 113 | 1806 |

### Cost fragility and capacity

- A 100bps assumed roundtrip cost changes one already explored ATR 10-session scenario from +4.37% (20bps) to -0.08%. Low turnover and fixed ticket size eliminated many nominal top-K choices.
- For 5-day Top-K10 at 50bps, ATR print-ledger return was about +0.61%, while Parkinson was about -1.05%; choice of horizon or Top-K **after seeing 2023** would be further data snooping.
- The realized account math uses cash and overlapping position limits, but uses historical opening and closing **prices**, not exchange order matches, tax/fee registry, latency, auction queue, limit-up/limit-down barriers or trading halt settlement records.
- Reported **0 blocked scenarios** means *the existing suspect corporate-action flags and this sampled price history* did not trigger an unknown holding-period exit in those runs. It does NOT independently certify absence of delistings, split errors, or exited securities outside the sampled history.

## Serious pre-trade data integrity blockers

- `official_reconcile_v08.py` tests date-exact historical FSC ISIN matches and detects reused tickers, but official authenticated records are not yet connected; coverage and split-adjusted return histories remain unverified.
- As per [FSC public API](https://www.data.go.kr/data/15043423/openapi.do), reference/issuance data for T are typically updated next business day after 13:00 KST, so they cannot be used to predict a T-close trade as if known at T.
- FSC issuer data may be restricted to **attribution + noncommercial use**; for commercial usage KSD licensing is needed.
- No independent measurement of investment risk: equity/mark-to-market drawdown path, halted/limit-locked sessions, sample selection, size/sector neutrality and undiscovered invalid outcomes still need to be covered.

**Verdict:** The software can now compute a capital-constrained **provisional** historical open/close price ledger; these are NOT verified actual trade results, NOT a clean backtest and NOT a strategy ready for live orders. Leave this PR draft. Never use 2026 for iterative formula tuning.