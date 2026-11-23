# K-SWING v2.1 — rising-stock indicator *pairs*

## Aim
Extend v2.0 single-indicator analysis to **three fixed two-indicator pairs**, asking whether a joint top/bottom quintile combination is enriched among stocks that **subsequently** rise by +3% or +5% over 5/10 sessions. The indicator observations are at signal close T; return labels are T+1 open to T+H close.

Predeclared pairs (all verified names in existing expanded factor catalog):
- `ta__stoch_rsi_14` × `ta__parkinson_vol_20` (momentum / volatility)
- `ta__macd_hist_pct` × `ta__parkinson_vol_20` (trend acceleration / volatility)
- `ta__ichi_cloud_top_gap` × `ta__parkinson_vol_20` (Ichimoku / volatility)

Each day's factor is ranked across the contemporaneous cross-section. Fixed high/low 20% combinations are compared against the same-day eligible baseline. Minimum 40 stocks per date, 30 observations per joint group; incomplete groups report NaN rather than pretend significance. 2019–20 and 2021–22 were already examined in older work, so directional consistency is only retrospective. No multiple-testing-corrected significance or net portfolio profit is asserted.

**Current data status:** historical per-symbol factor matrices are held privately and are not accessible in this GitHub environment. Only synthetic contract tests can run. The first real empirical pair rankings require the user/operator to supply private factor-matrix parquet files; never commit them to GitHub or upload raw data into CI artifacts.

Run locally: `python -m research.k_swing.winner_pairs_v21 --parts /private/factor_matrix_part_*.parquet --private-output /private/winner_pairs_v21`

**NO-GO** until official identity/corporate actions, historical costs, liquidity and genuinely independent confirmation. 2026 remains locked, no live trades, no main merge.
