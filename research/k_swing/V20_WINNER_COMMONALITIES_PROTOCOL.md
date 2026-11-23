# K-SWING v2.0 — rising-stock indicator commonalities

## Research question
Which **indicators observed at close T** are disproportionately high or low among stocks that subsequently gain at least **+3% or +5%** from **T+1 open to T+5 or T+10 close**? This is a *descriptive case-control comparison*, not a prediction model or proof that the indicators cause gains.

## Predeclared analysis
- Reuse **existing v0.4 factor matrix**: 18 legacy + approximately 170 technical indicators, without inventing new features or pulling fresh quotes.
- Split 2019–20 vs 2021–22. Both have already been used for strategy research: sign agreement is descriptive, **not independent out-of-sample validation**.
- Within each signal date, rank every factor across stocks. Compare top and bottom 20% to the same-day unconditional probability of a +3%/+5% future rise.
- Report winner-rate lift, top-minus-bottom percentage-point difference, per-date sample counts and whether the direction matches across the two historical periods.
- **Avoid leakage:** factor inputs at or before T; label only after T+1 open. No current winners used to pick their own prior factors; do not claim a strategy's entry price or actual fills.
- No strategy selection or portfolio simulation in this phase. Multiple-testing corrections and issuer-event reconciliation remain mandatory before any alpha claims.

## How to run privately
`python -m research.k_swing.winner_profiles_v20 --parts /private/factor_matrix_part_*.parquet --private-output /private/winner_profiles_v20`

Keep symbol-level matrices, date traces and private factor CSVs off public GitHub/Actions artifacts. Only aggregate `aggregate_manifest.json` can be shared after reviewing source licenses.

## Expected research themes (hypotheses, NOT observed findings)
1. **Trend**: 20/60-day price position, Ichimoku cloud gap, moving-average slope.
2. **Volume/liquidity**: volume surge, turnover acceleration, volume-price confirmation.
3. **Volatility**: ATR compression vs breakout, recent drawdown and range expansion.
4. **Momentum/reversal**: relative strength and short-term pullback interactions.
5. **Market regime**: benchmark trend and market-wide breadth, where present in the matrix.

Important: A feature can be common among future winners yet also common among losers. The relevant quantity is *enrichment against a same-day comparison group*, not merely high average factor values in winners.

## Current result
**NO EMPIRICAL WINNER-FACTOR RESULT YET.** The screened historical factor parquet is private and was not provided in this run. GitHub Actions run synthetic logic tests only. 2026 is locked; no real orders or main merge.
