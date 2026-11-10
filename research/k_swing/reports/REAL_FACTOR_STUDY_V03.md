# K-SWING v0.3 — real-data factor validation (exploratory)

**Run:** [GitHub Actions #42862245085](https://github.com/joong0712/global-macro-bottom-up-financial-simulator/actions/runs/42862245085) — successful; **28 unit tests passed**, 40 nonfatal Python warnings.

**Data source:** FinanceData/marcap pinned at `94c138df4bf7376be8d28f979edb14020e2a547a`.

## Fixed experimental design

- **Train:** 2019–2022; **validation:** 2023; **independent held-out test:** 2024–2025.
- Horizon: **5 / 10 exchange sessions**; signal at T close, hypothetical entry T+1 open, exit T+H close.
- Eligibility known by signal T: close at least 1,000 KRW, daily turnover at least 100,000,000 KRW, positive volume, quarantine-free T; missing or unsafe holding windows removed.
- Ten-session purges before the 2022, 2023 and 2025 study boundaries prevent cross-period future labels.
- **18** prespecified factors; top five and their ranking direction were frozen using training data only.
- Top-10 per signal day by training-chosen factor direction; benchmark is average of all eligible stocks on that same day.
- Returns and excess returns are arithmetic **mean per signal day**, not a compounded portfolio or CAGR.
- Full study processed **4,092,153 ticker-date records**, **60,804 factor/horizon/date observations**, and **108 factor/horizon/split aggregate metric records**.

## Important first finding

For the examined period, **lower volatility** — lower ATR/close, lower realized volatility, and narrower Bollinger Bands — tended to be associated with higher 5- and 10-session forward-return ranks.
All 10 of the train-preselected factor/horizon combinations maintained positive oriented mean Rank IC in the 2024–25 test.
However, that ranking association **did not translate into consistent Top-10 excess returns across periods**; notably all five training-selected 10-session factor cohorts underperformed their eligible-universe benchmark in 2023 validation.

### Five-session top factors selected from training

| Factor (choose low values) | Train Rank IC | 2023 Rank IC | 2024–25 Rank IC | 2023 Top-10 gross excess | 2024–25 Top-10 gross excess |
|---|---:|---:|---:|---:|---:|
| volatility_20 | +0.0868 | +0.0979 | +0.1137 | -0.150%p | +0.101%p |
| atr_pct_14 | +0.0864 | +0.0947 | +0.1163 | -0.069%p | +0.160%p |
| bb_width_20 | +0.0673 | +0.0740 | +0.0899 | -0.051%p | +0.066%p |
| sma_gap_20 | +0.0572 | +0.0397 | +0.0364 | -0.896%p | +0.293%p |
| sma_gap_5 | +0.0557 | +0.0516 | +0.0280 | -0.952%p | -0.226%p |

### Ten-session top factors selected from training

| Factor (choose low values) | Train Rank IC | 2023 Rank IC | 2024–25 Rank IC | 2023 Top-10 gross excess | 2024–25 Top-10 gross excess |
|---|---:|---:|---:|---:|---:|
| atr_pct_14 | +0.0983 | +0.1087 | +0.1361 | -0.166%p | +0.337%p |
| volatility_20 | +0.0957 | +0.1095 | +0.1315 | -0.448%p | +0.121%p |
| bb_width_20 | +0.0739 | +0.0843 | +0.1038 | -0.122%p | +0.076%p |
| ema_gap_12_26 | +0.0593 | +0.0333 | +0.0315 | -0.213%p | +0.049%p |
| ret_20 | +0.0556 | +0.0362 | +0.0350 | -1.483%p | +0.167%p |

All negative original Rank IC directions were flipped using training-only decisions (the tested hypothesis is selecting *low* factor values). Do not mistake positive oriented IC for an annualized investment return.

### Detailed 10-session ATR illustration, 2024–25 test

- Signal days: **476**, each with 10 selected tickers (the same ticker may repeat on many dates).
- Hypothetical Top-10 **average gross forward return +0.406%** vs corresponding eligible-universe **+0.069%**.
- Top-10 mean **gross excess +0.337 percentage points** per *overlapping signal window*.
- A crude fixed **20 bps total roundtrip** subtraction yields **+0.206% per window**; this is NOT a realizable portfolio net return.
- In **2023 validation**, the identical direction produced **-0.166 percentage points of gross excess**.

## Interpretation and research limitations

1. These are exploratory forward-label/Rank-IC statistics. They do not model positions, overlapping holdings, buying power, transaction-time fills, price limits, order books, execution delay, individual taxes or delisting outcomes.
2. Corporate actions and adjusted-price methodologies remain unverified. Incomplete historical security-master and delisting coverage can materially alter conclusions, despite the v0.2 suspected-event quarantine.
3. The three volatility factors are conceptually similar; their signal is not independent evidence of three different discoveries. Industry/size/risk exposures and time autocorrelation were not adjusted.
4. There are 18 factors and two horizons; no multiple-comparison correction, statistical confidence interval, block bootstrap, walk-forward retuning or risk-neutral regression has been executed.
5. 2024–25 has now been examined. Future modifications based on these results must use a **new untouched confirmation period** (e.g., separate 2026 holdout or future observations), not re-label 2024–25 as untouched.
6. Study excludes signal-close share price below 1,000 KRW and turnover below KRW 100m; that reduces low-liquidity exposure but does not guarantee next-open tradeability.

## Conclusions

**The first real-data factor analysis was implemented and ran successfully; it found a potentially reproducible cross-sectional *low-volatility ranking association*, not a proven tradable alpha or a newly invented algorithm.**
Before moving to new formula discovery, verify official security identities/corporate-action-adjusted price returns, evaluate industry and market beta controls, and implement a capital-constrained execution backtest.

**Result archive (aggregate metrics only):** [K-SWING v0.3 Actions artifact](https://github.com/joong0712/global-macro-bottom-up-financial-simulator/actions/runs/42862245085/artifacts/13786847571).
