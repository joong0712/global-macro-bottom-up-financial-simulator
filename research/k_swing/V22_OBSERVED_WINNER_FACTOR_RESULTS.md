# K-SWING v2.2 — observed 2019–22 rising-stock commonalities

## Source and scope
GitHub Actions successful run: https://github.com/joong0712/global-macro-bottom-up-financial-simulator/actions/runs/45115507380

- 166 hash-sampled securities, 134,266 precomputed factor-panel rows, historical source FinanceData/marcap (not independently official/corporate-action adjusted)
- 736 factor × horizon × threshold aggregate rows, of which 430 had the same top-vs-bottom direction across two previously explored periods
- 48 two-factor × horizon × threshold × quadrant aggregate rows, of which 17 showed positive lift over the eligible reference in both periods
- These are correlated, multiple-tested *descriptive* observations, not 430 unique predictive factors or 17 independently validated strategies

## Single-factor commonality: 5 sessions, >=+5% from T+1 open
Values below are high-quintile minus low-quintile **percentage points** of future-rise frequency, NOT returns.

| Factor | 2019–20 pp | 2021–22 pp |
|---|---:|---:|
| ta__atr_wilder_pct_7 | +12.65 | +10.66 |
| legacy__atr_pct_14 | +12.92 | +10.51 |
| ta__bb_bandwidth_50 | +11.71 | +10.23 |
| ta__realized_vol_10 | +10.97 | +10.19 |
| ta__parkinson_vol_20 | +13.06 | +10.13 |

Dominant recurring feature family is **high historical volatility / wide price ranges**, which can increase both upward and downward tail-event frequencies. This is not evidence of positive expected return.

## Two-factor commonality: 5 sessions, >=+5% rise
Fixed high/high quadrants: both factors in their same-day top quintile. Baseline is the contemporaneous eligible universe, not the low/low group.

| Pair | 2019–20 winner rate | 2021–22 winner rate | 2019–20 excess pp | 2021–22 excess pp |
|---|---:|---:|---:|---:|
| Ichimoku cloud top gap × Parkinson volatility | 23.7% | 22.3% | +4.81 | +6.53 |
| MACD histogram pct × Parkinson volatility | 23.7% | 22.9% | +4.78 | +7.02 |
| Stoch RSI 14 × Parkinson volatility | 25.8% | 21.8% | +6.83 | +5.86 |

The two periods are already explored, so they are **not independent out-of-sample confirmation**. Overlapping 5/10-day labels and repeated dates/stock observations reduce effective sample size. Corporate-action and survivorship coverage are not independently certified; no multiple-comparison adjustment, negative-tail comparison, or after-cost portfolio PnL is established. **NO-GO for deployment.**

## Next rigorous test
1. For high-volatility cohorts, compare downside tails (<=-3%, <=-5%), median/mean net forward returns, and volatility-adjusted expected return against matched eligible controls.
2. Test whether a second indicator adds incremental information *within the same high-volatility subset*, rather than simply rediscovering the volatility effect.
3. Date-block bootstrap with multiple-testing correction and frozen hypotheses, then independent official identity/corporate-action/fill reconciliation.
4. Preserve locked 2026 holdout; no orders or main merge.

Source aggregate artifact (retention limited): https://github.com/joong0712/global-macro-bottom-up-financial-simulator/actions/runs/45115507380/artifacts/14791013335
