# K-SWING v0.4 — 188-feature historical pilot (2019–2023)

## Execution and reproducibility

- **Result:** successful GitHub Actions run [#42871531605](https://github.com/joong0712/global-macro-bottom-up-financial-simulator/actions/runs/42871531605).
- **Aggregated results ZIP:** [Actions artifact 13790018461](https://github.com/joong0712/global-macro-bottom-up-financial-simulator/actions/runs/42871531605/artifacts/13790018461) (short retention).
- **Code:** research/k_swing/factor_pilot_v04.py. No production web files modified.
- Source: FinanceData/marcap pinned snapshot 94c138df4bf7376be8d28f979edb14020e2a547a.
- Deterministic, survival-independent ticker-code hash modulus=8 sample: **328 ticker codes with eligible bars**, **274,055 signal ticker-day rows** and **1,213 signal dates**.
- **188 calculated features** (170 expanded + 18 existing; correlated/redundant), 5-day and 10-day forward returns.
- **455,969 daily factor/horizon/date observations**; 752 aggregated factor/horizon/split rows.
- Train 2019–2022 (978 evaluable dates per selected factor); 2023 exploratory validation (235 evaluable dates).
- Fixed Top-K list: **1, 3, 5, 10, 20**; top-five factors and orientation determined on training data only.
- No 2024–2025 return re-evaluation; **2026 remained locked**.

## Five-day training-selected features and validation

| Feature (lower is favorable) | 2019–22 oriented train Rank IC | 2023 oriented Rank IC | 2023 Top-10 gross excess per signal window |
|---|---:|---:|---:|
| ATR Wilder / close, 7d | +0.0870 | +0.0897 | +0.06%p |
| Parkinson volatility, 20d | +0.0847 | +0.0914 | +0.11%p |
| Realized volatility, 10d | +0.0843 | +0.0783 | -0.14%p |
| Garman–Klass volatility, 20d | +0.0834 | +0.0912 | +0.07%p |
| Legacy ATR / close, 14d | +0.0832 | +0.0802 | +0.02%p |

## Ten-day training-selected features and validation

| Feature (lower is favorable) | 2019–22 oriented train Rank IC | 2023 oriented Rank IC | 2023 Top-10 gross excess per signal window |
|---|---:|---:|---:|
| ATR Wilder / close, 7d | +0.0972 | +0.1058 | -0.04%p |
| Realized volatility, 60d | +0.0952 | +0.1073 | -0.14%p |
| Parkinson volatility, 20d | +0.0940 | +0.1087 | -0.02%p |
| Legacy ATR / close, 14d | +0.0931 | +0.0979 | -0.06%p |
| Garman–Klass volatility, 20d | +0.0927 | +0.1086 | -0.01%p |

**Sign check:** all five train-selected factors have a positive oriented mean Rank IC in the 2023 pilot for both holding horizons. However at K=10, only **4/5 five-day** and **0/5 ten-day** factor cohorts have positive average gross excess.

## Top-K sensitivity example: Parkinson volatility (ten-day, 2023)

| K chosen per day | Average gross excess vs equal-weight eligible sample |
|---:|---:|
| 1 | +0.67%p |
| 3 | +0.59%p |
| 5 | +0.24%p |
| 10 | -0.02%p |
| 20 | -0.12%p |

These K values are **exploratory diagnostics, not a basis to retrospectively pick K=1 or K=3**. Selection of K after viewing 2023 invalidates any claim that 2023 was independent confirmation. The values are average overlapping future-return LABELS (T+1 hypothetical open to T+H close), not realized portfolio returns.

## Interpretation and limitations

1. All top-ranked factors are correlated descriptions of volatility. The pilot did not discover multiple independent alpha mechanisms.
2. Pilot used a non-representative hashed subset and does not adjust for sector, market beta, size, leverage or selection bias.
3. Corporate actions, delistings, security identifier reuse and exact instrument types are not independently verified; source prices are not certified corporate-action-adjusted.
4. No execution/fillability model, real fees/tax timing, overlapping position accounting, slippage, compounding, risk constraints, or risk-adjusted portfolio PnL was simulated.
5. 2023 was previously inspected for legacy v0.3 factors, so it is **REUSED EXPLORATORY VALIDATION**, not an untouched holdout.
6. With 188 correlated factors × 2 holding periods × multiple K, apparent successes can easily arise by multiple testing; no FDR or clustered inference applied yet.
7. Do not open 2026 confirmation results until a fixed hypothesis, stock universe, corporate-action adjustments, execution model and evaluation procedure are preregistered.

**Conclusion:** broad-factor computation and sampled retrospective evaluation work end-to-end; the recurring low-volatility Rank IC association is interesting but does NOT establish a tradable swing strategy. The failure of the ten-day Top-10 cohort to outperform the eligible-universe baseline in 2023 is an important negative finding.
