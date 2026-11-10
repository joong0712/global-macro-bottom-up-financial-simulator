# K-SWING v0.6 — verified correlated-factor clusters and 2019–23 yearly Rank IC

## Reproducible successful run

- [GitHub Actions #42879924976](https://github.com/joong0712/global-macro-bottom-up-financial-simulator/actions/runs/42879924976) — **successful**.
- [Aggregated results artifact](https://github.com/joong0712/global-macro-bottom-up-financial-simulator/actions/runs/42879924976/artifacts/13794150971) — downloadable for limited retention.
- Unit tests for clustering and annual IC: **5 passed** (the full baseline suite is checked independently in previous CI runs).
- FinanceData/marcap pinned, 2017–23 downloaded and QC checked on a temporary runner; **no raw prices, ticker selections, private security panels or source events uploaded**.
- Hash-based sample (modulus 16, independent of stock survival): **170 distinct ticker codes**, **145,231 eligible signal ticker-days**, **1,233 observed signal dates**, 2019–2023.

## Indicator redundancy analysis

Applied to **2019–2022 training only** (no 2023/2024/2025/2026 labels):

- **188 named variables** grouped into **119 absolute-correlation connected components** at |Pearson correlation of within-date percentile ranks| ≥ **0.95**.
- **69 possibly redundant feature variants**, including **84 singleton clusters** and **35 multi-feature clusters**.
- **92 high-correlation edges** between pairs of factor variants.
- Correlation sample: **198 trading dates / 23,180 ticker-day rows** (every fifth observed training session).
- Largest cluster: **18 moving-average/trend variants**, representative chosen from training IC: `ta__ema_gap_50`.
- ATR family of **5 strongly related variants** grouped together, representative: `ta__atr_wilder_pct_7`.
- Representatives determined ONLY by maximum absolute IC in historical training, not reused 2023 validation.

**Methodology note:** graph connected-components at correlation 0.95 do not guarantee every pair within a multi-node group has correlation 0.95. This is screening for potential redundancy, not proof of independent causal factors or justification for dropping 69 features automatically.

## Annual stability of 30 train-selected factor/horizon pairs

Historical factor direction and the top 15 factor candidates per horizon were fixed from 2019–2022 training. Daily cross-sectional Rank IC for the 170-code sample was then summarized separately for 2019, 2020, 2021, 2022 and **already-inspected 2023**.

| Horizon | Train-selected factor/horizon pairs | Positive mean oriented IC in all 4 available training years | Positive again in reused 2023 |
|---|---:|---:|---:|
| 5 trading days | 15 | 15 / 15 | 15 / 15 |
| 10 trading days | 15 | 15 / 15 | 15 / 15 |

Example factors in the smaller hash sample:

| Factor | 2023 reused oriented Rank IC (5d) | 2023 reused oriented Rank IC (10d) |
|---|---:|---:|
| Garman–Klass vol, 20d | +0.0990 | +0.1134 |
| Parkinson vol, 20d | +0.0980 | +0.1120 |
| Wilder ATR / price, 7d | +0.0963 | +0.1095 |

These IC numbers differ from the larger v0.4 hash modulus=8 sample because the instrument population changed (v0.6 modulus=16). This does **not** imply predictive improvement.

## Critical interpretation

1. These **30 were preselected** based on the 2019–2022 data; consequently the positive within-training sign is vulnerable to selection bias.
2. Most top indicators are highly correlated variants of *volatility*. Thirty positive IC records are NOT thirty independent discoveries.
3. Positive annual Rank IC signs do NOT establish portfolio excess profits, executable alpha, independent statistical significance, or resistance to tail-risk crashes.
4. Forward return labels overlap across adjacent days; naively treating daily values as independent observations would overstate significance.
5. Historical corporate-action adjustments, delistings, instrument types and sectors remain incompletely certified.
6. The 2023 period was already inspected and cannot serve as pristine holdout for tuning; **2026 remains unopened**.

## Next gates

- Point-in-time official KRX/KIND corporate actions, delisted stock history and sector classifications.
- Correlation-cluster representatives vs their nonrepresentatives tested without choosing by already-inspected test performance.
- Time-block-bootstrap and multiple-testing/FDR-aware significance claims.
- Capital-accounted, trade-fillable backtest with turnover, Korean tax regime, risk and drawdown.
- Lock a fixed algorithm prior to opening 2026 independent confirmation once.

Production Streamlit web app and main branch remain unchanged; all changes live under `research/` and `.github/workflows/`.
