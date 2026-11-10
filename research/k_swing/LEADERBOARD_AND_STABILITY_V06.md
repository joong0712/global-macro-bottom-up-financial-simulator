# K-SWING v0.6 — parallel leaderboard, redundancy and yearly stability

## Three independent investigation tracks

1. **188 × (5/10 trading days) × (K=1/3/5/10/20) leaderboard**: a fully labeled retrospective ranking using the already-computed aggregated historical pilot (2019–22 train, 2023 previously inspected). Never turn the top of a reused 2023 ranking into claims of independently validated alpha.
2. **Correlated feature redundancy**: normalize each indicator to its cross-sectional percentile rank per trading date in 2019–22 TRAIN only; compute pairwise correlations and 0.95 absolute-correlation graph connected components. Keep a single representative per cluster selected by TRAIN absolute Rank IC. Correlated clusters are not proof the excluded features are identical.
3. **Annual stability**: for the top 15 factors per 5- and 10-day horizon chosen using 2019–22 TRAIN only, record oriented daily Rank IC separately for each of 2019, 2020, 2021, 2022, and reused exploratory 2023. A stable sign is descriptive, not a multiple-testing-corrected p-value.

### Reproducibility

Public GitHub Actions aggregate data source: [v0.4 pilot run #42871531605](https://github.com/joong0712/global-macro-bottom-up-financial-simulator/actions/runs/42871531605). The v0.6 ranking CI uses its aggregate factor CSV and training rank CSV, with no OHLCV download.

Historic redundancy/stability CI re-acquires 2017–23 original KRX-derived marcap snapshot with 2024–26 omitted, applies the existing quality gate, and uses a deterministic SHA-256 ticker code sample (modulus=16) to limit memory and runner time. Training factor correlations use 2019–22 observations ONLY.

### Strict research limitations

- These rankings are **post-hoc** on previously inspected 2023. The 'winner' is a descriptive exploratory maximum among many comparisons and is likely inflated by multiple testing.
- Net approximations simply subtract assumed 20/50/100bp costs per trade from gross EXCESS vs a cost-free eligible-stock benchmark. They are **not actual net PnL**.
- No complete corporate-action-adjusted returns, historical sector/classification mapping, delisting universe certification, true exchange price-limit fills, financing or capital ledger.
- Overlapping 5/10-session labels violate independent signal assumptions; yearly mean IC/positive-year counts are not robust statistical significance tests.
- 2026 untouched confirmation window remains locked. No v0.6 code reads it.
- Production Streamlit frontend and main branch remain unchanged.

### Remaining plan

Before automatic new alpha formulas or any confirmed strategy claims: official corporate action/universe accuracy, independent sector effects, fillability/cash simulation, statistical multiple-testing correction, preregistered finalist, then one genuine untouched 2026 confirmation.
