# K-SWING v0.6 — all 188 technical factors ranked across 1,880 exploratory combinations

**Provenance:** real 2019–2022 training and *previously inspected* 2023 exploratory validation; derived exclusively from [v0.4 aggregate-factor run #42871531605](https://github.com/joong0712/global-macro-bottom-up-financial-simulator/actions/runs/42871531605).

**Reproducible leaderboard job:** [GitHub Actions run #42879271187](https://github.com/joong0712/global-macro-bottom-up-financial-simulator/actions/runs/42879271187) succeeded. Its outputs have 1,880 rows (188 factors × 2 horizons × 5 K), including training vs 2023 mean Rank IC, train/2023 gross benchmark excess, and hypothetical 20/50/100bps costs.

## 2023 posthoc gross-excess winners (NOT investable or independently confirmed)

| Future holding period | Picks per signal day | 2023 retrospective leader (train-chosen direction) | Mean gross excess per overlapping forward-return window |
|---:|---:|---|---:|
| 5 days | 1 | NVI 20-session return | +1.953%p |
| 5 days | 3 | Ichimoku current-cloud thickness | +2.126%p |
| 5 days | 5 | Ichimoku current-cloud thickness | +1.421%p |
| 5 days | 10 | Parabolic SAR price distance | +0.612%p |
| 5 days | 20 | 100-session SMA gap | +0.511%p |
| 10 days | 1 | NVI 20-session return | +4.013%p |
| 10 days | 3 | Ichimoku current-cloud thickness | +2.633%p |
| 10 days | 5 | Ichimoku current-cloud thickness | +2.122%p |
| 10 days | 10 | 60-session return kurtosis | +0.977%p |
| 10 days | 20 | 60-session return kurtosis | +0.773%p |

**NVI single-stock selection had NEGATIVE training-period gross excess:** -0.509%p (5d) and -0.562%p (10d). The dramatic 2023 single-stock top rank should therefore be treated as potentially unstable and selection-biased.

## Stability cross-check available in previously published aggregate files

Number of 188 factors with **positive gross excess in both training (2019–22) and 2023**:

| Horizon | K=3 | K=10 |
|---|---:|---:|
| 5d | 65 / 188 | 69 / 188 |
| 10d | 41 / 188 | 37 / 188 |

This is not a significance test: the factor direction was trained on 2019–22, these features are correlated, multiple K were inspected, 2023 is reused and future holding labels overlap. Real trading also has transaction costs and order capacity, not captured in these gross-excess quantities.

## Independent continued work

- **Feature redundancy clustering:** training-only 2019–22 feature rank correlations with connected-components threshold |r|≥0.95; never select cluster representatives on 2023.
- **Annual-stability breakdown:** daily Rank IC per 2019, 2020, 2021, 2022 and reused 2023 for training-picked factors, with missing-market data excluded.
- Workflows use separate GitHub Actions jobs to avoid blocking this completed fast leaderboard.

**2024–2026 data were not accessed in this v0.6 step.** Production Streamlit website and `main` remained unchanged. No stock-level data or raw prices were published.
