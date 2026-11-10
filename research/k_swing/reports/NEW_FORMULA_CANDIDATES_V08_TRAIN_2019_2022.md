# K-SWING v0.8 — 12 deterministic research candidate expressions, training 2019–22

## Confirmed actual historical experiment

- Three parallel GitHub Actions jobs all passed: https://github.com/joong0712/global-macro-bottom-up-financial-simulator/actions/runs/42894438518
- Training-only candidate aggregate ZIP: https://github.com/joong0712/global-macro-bottom-up-financial-simulator/actions/runs/42894438518/artifacts/13800182016
- Historical daily bars 2017–2022, screened with existing v0.2. Sample comprised **114,580 eligible ticker-days and 978 trading dates** in signal years 2019–2022.
- 12 authored, transparent mathematical combinations drawn from eight pre-existing causal technical indicators, two holding horizons (5/10 sessions) = **24 candidate-horizon rows**. There was no autonomous symbolic regression/generative search over arbitrary expressions.
- Signal orientation fixed using **2019–2020**, and **2021–2022** used only as INTERNAL descriptive evaluation. All four years have previously informed baseline research and are **not pristine holdout sets**.
- **2023, 2024, 2025 and 2026 OHLCV were not loaded by this particular new-expression study.**

## Strongest apparent training-only association

Factor `c08_low_vol_contraction`: Bollinger bandwidth contraction combined with Parkinson price-range volatility, both previously known features.

| Return horizon | Discovery 2019–20 oriented Rank IC | Internal 2021–22 oriented Rank IC |
|---|---:|---:|
| 5 trading sessions | +0.0559 | +0.0881 |
| 10 trading sessions | +0.0496 | +0.1109 |

These are cross-sectional rank association metrics, NOT percent gains, not transaction-tax-adjusted returns or realized portfolio alpha. Correlation may be partly explained by the existing documented low-volatility effect.

## Why 24 positive-looking combinations do not mean 24 discoveries

- All **24/24** candidate/horizon rows have positive oriented mean IC in both internal training subperiods. Direction was explicitly chosen based on 2019–20 values, so positivity in that part is mechanically favored.
- `c01_low_vol_positive_momentum` and `c02_low_vol_negative_momentum` are **exact opposite formulas**. After sign orientation their **four annual IC series are identical**, in both 5- and 10-session tests. These MUST be deduplicated before counting unique research hypotheses.
- Other combinations share ATR, Parkinson, RSI, Ichimoku, MACD and turnover inputs, and are not statistically independent.
- We do NOT claim an improvement over the best existing baseline: an exact equal-sample, equal-filter, same-date comparison with ATR/Parkinson plus proper block inference and market/industry effects is pending.
- The 2021–22 sign stability is useful to prioritize falsification but is not independent replication because the whole historical era was already analyzed.

## Research progression

1. Obtain/verify official date-exact ISIN and company-action source history, delisted terminal outcomes and unadjusted-to-adjusted returns.
2. Apply baseline-versus-candidate incremental Rank IC and trade-return comparison on exactly matched securities/dates, avoiding correlated-factor double counting.
3. Validate turnover/slippage, tax regime and open-auction fillability with a self-financing portfolio; the current price-print ledger is explicitly provisional.
4. Precommit one finalist formula, direction, horizon and market/cost filters before opening 2026 holdout once, and paper trade before real capital.

No production web/main edits, and no real brokerage orders.