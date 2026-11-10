# K-SWING v0.9 — actual 12-candidate same-security incremental Rank IC test

## Provenance

- [Independent GitHub Actions job succeeded](https://github.com/joong0712/global-macro-bottom-up-financial-simulator/actions/runs/42897397840).
- [Public aggregate artifact](https://github.com/joong0712/global-macro-bottom-up-financial-simulator/actions/runs/42897397840/artifacts/13800993039). Only aggregate 12×2×subperiod stats, no security-level price/outcome files.
- FinanceData/marcap pinned private 2017–2022 history, 2019–2022 signal dates, **978 eligible signal dates**. No 2023–2026 records read in this candidate job.
- 12 previously authored bounded formulas × 5/10 sessions = **24 candidate/target pairs**.
- Candidate direction and stronger historical baseline ATR7 vs Parkinson20 selected using **2019–2020 only**; the 2021–2022 paired check is internal and **not untouched out-of-sample**.
- Every candidate/ATR/Parkinson comparison uses exactly the same stock-date rows with observable factor and future label values; no different sample advantage, but missing future outcomes may still cause informative censoring.

## Findings: negative incremental comparison

- **0 / 24 candidate-horizon pairs** had a positive mean 2021–2022 paired Rank IC gain over their training-selected low-volatility baseline.
- **8 / 24** had a numerically positive partial IC after residualizing candidate & forward-return ranks on both baseline factor ranks; **0 / 24** had a 20-session moving-block 95% partial-IC interval wholly above zero.
- There is no demonstrated independent improvement of any new formula over baseline ATR7/Parkinson20 in this matched historical internal comparison.

### Previously highest-looking candidate — c08 volatility contraction

| Horizon | Candidate oriented IC, 2021–22 | Same-name ATR7 baseline oriented IC | Paired difference | 20-session block interval for difference | ATR+Parkinson controlled partial IC | 95% block interval for partial IC |
|---|---:|---:|---:|---|---:|---|
| T+5 sessions | +0.0882 | +0.1011 | **-0.0129** | [-0.0214, -0.0048] | -0.0098 | [-0.0296, +0.0080] |
| T+10 sessions | +0.1107 | +0.1260 | **-0.0153** | [-0.0247, -0.0058] | -0.0090 | [-0.0317, +0.0159] |

Evaluable internal 2021–2022 days for c08: **484**; matched stock/day observations **59,744 (5d) / 59,588 (10d)**. The negative paired intervals are an exploratory sensitivity check, NOT a selectivity-adjusted hypothesis rejection.

## What this means

1. The seemingly promising +0.1109 c08 Rank IC from the prior 2019–22 formula study does **not** mean a superior algorithm. The baseline ATR7 on the same samples had +0.1260 IC.
2. Statistical relationship is not capital-accounted investor profit; no actual fill/tax/corporate-action-adjusted return modeled in this candidate comparison.
3. Multiple comparisons, correlated factor variants, repeated historical research access, overlapping future outcome windows and missing delisted stocks invalidate a claimed discovery even if a pair appears numerically strong.
4. This negative result justifies **not promoting any of the twelve formulas** to final candidate or using the 2026 untouched test to rescue them.

## Next research directions

- First independently verify official historical ISIN/ordinary-share universe, rights/splits, delisting payouts and corrected history.
- Investigate entirely different factor mechanisms (not further tuning variants of volatility) with preregistered hypotheses and causal data-vintage tracking: residual trends, industry-relative information, after-publication DART financial signals, dated institutional/foreign flows.
- Use training-only full universe and reproducible risk/cost ledger; set the entire discovery/validation scheme before a one-time 2026 confirmation. Do not chase 2023 leaderboard winners.

**Verdict: negative incremental evidence; no new tradable alpha discovered.**
