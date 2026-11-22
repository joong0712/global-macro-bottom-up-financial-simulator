# K-SWING v1.3 — Ichimoku + moving-average timing research: actual CI results

## Final decision: NO-GO — none of the 24 strategy/entry/holding combinations is profitable in both already-inspected historical research periods

- Verified completed all-green CI: https://github.com/joong0712/global-macro-bottom-up-financial-simulator/actions/runs/45054895911
- Source branch: research/k-swing-v13-ichimoku-ma-timing, Draft PR #11. Six strategy jobs, each eight combinations (2 subperiods x 2 entry delays x 2 holding periods) = 48 scenario rows.
- Historical input: KOSPI/KOSDAQ 2017-2022 with strict unsafe-bar and 253-session continuity; deterministic ticker hash modulo 16 (166 sampled securities). Signal dates: 2019-01-01 through 2020-12-15 and 2021-01-01 through 2022-12-15.
- Funding and cash: 100 million KRW initial cash per scenario; max 5 million KRW per stock, 10 stocks open; assumed 50bp roundtrip costs; 5 or 10 sessions including entry, -3% stop / +8% take; no future leakage, true next-day or second-day historical open print if available. **Not actual exchange fills.**
- All 48 result scenarios returned HYPOTHETICAL_OHLC_ONLY; none blocked by an unresolved holding in this selected sample. The absence of blocked holdings does NOT certify corporate-action/delisting completeness.
- 2019-20 and 2021-22 periods had already been explored in earlier v1.0-v1.2 research, so both are **reused developmental evidence, not a valid unseen out-of-sample proof**.
- 2023-2026 datasets were not read.

## Every simulated scenario (two separate cash accounts, NOT combined)

All numbers below are **hypothetical net cash account returns (%)**, each scenario charged assumed roundtrip 0.50%. T+ refers to how many trading-session opens after the signal-day close the buy is placed. H = maximum trading sessions held including entry.

| Frozen method | Buy delay | Hold H | 2019-20 net return | 2021-22 net return | Closed 2019-20 | Closed 2021-22 |
|---|---:|---:|---:|---:|---:|---:|
| ichi_cloud_breakout | T+1 | 5 | -2.45% | -2.17% | 73 | 63 |
| ichi_cloud_breakout | T+1 | 10 | -2.60% | -2.91% | 73 | 62 |
| ichi_cloud_breakout | T+2 | 5 | -2.76% | -3.91% | 73 | 62 |
| ichi_cloud_breakout | T+2 | 10 | -3.06% | -4.82% | 73 | 60 |
| ichi_kijun_reclaim | T+1 | 5 | -8.20% | -8.25% | 193 | 249 |
| ichi_kijun_reclaim | T+1 | 10 | -9.73% | -7.91% | 188 | 249 |
| ichi_kijun_reclaim | T+2 | 5 | -10.81% | -17.15% | 190 | 247 |
| ichi_kijun_reclaim | T+2 | 10 | -11.54% | -18.20% | 187 | 246 |
| ma_5x20 | T+1 | 5 | -9.15% | -8.99% | 169 | 204 |
| ma_5x20 | T+1 | 10 | -9.44% | -9.44% | 169 | 203 |
| ma_5x20 | T+2 | 5 | -4.35% | -5.02% | 169 | 204 |
| ma_5x20 | T+2 | 10 | -5.93% | -6.72% | 166 | 201 |
| ma20_reclaim | T+1 | 5 | -7.36% | -15.32% | 266 | 352 |
| ma20_reclaim | T+1 | 10 | -9.36% | -14.38% | 265 | 344 |
| ma20_reclaim | T+2 | 5 | -8.05% | -14.97% | 265 | 344 |
| ma20_reclaim | T+2 | 10 | -7.96% | -15.00% | 261 | 332 |
| ichi_ma_confirm | T+1 | 5 | -0.39% | -1.06% | 35 | 30 |
| ichi_ma_confirm | T+1 | 10 | -0.28% | -1.11% | 35 | 29 |
| ichi_ma_confirm | T+2 | 5 | -0.71% | -2.46% | 35 | 30 |
| ichi_ma_confirm | T+2 | 10 | -1.21% | -2.93% | 35 | 29 |
| vcr_trend_control | T+1 | 5 | -3.57% | -0.04% | 30 | 37 |
| vcr_trend_control | T+1 | 10 | -3.57% | -0.39% | 30 | 37 |
| vcr_trend_control | T+2 | 5 | +0.82% | -1.91% | 30 | 37 |
| vcr_trend_control | T+2 | 10 | +0.80% | -2.07% | 30 | 37 |

## What actually changed with indicator-derived entry timing?

- Most stable (least negative **minimum return across both periods**) is ichi_ma_confirm + buy T+1 + hold max 5: **-0.39%** (MDD -1.89%, 35 exits) in 2019-20 and **-1.06%** (MDD -1.43%, 30 exits) in 2021-22. Still NEGATIVE in both; NOT a trade-ready signal. Its smaller cash losses are confounded by very low trade frequency and lower risk exposure.
- Pure cloud breakout performs better when buying at T+1 rather than T+2 and holding 5 rather than 10: **-2.45% / -2.17%**, 73/63 trades. Again no alpha.
- 5/20 SMA cross appears less negative when delayed to T+2 and held 5: **-4.35% / -5.02%** vs T+1 5 at -9.15% / -8.99%. This is a *hypothesis* about momentum confirmation, not a proven profitable delay rule.
- Prior VCR+trend control's T+2 5-day experiment was positive in **one** old period (+0.82%) but negative in the other (-1.91%); cannot pass two-period profit gate. T+1 5 replicates prior research -3.57% / -0.04%, useful for reproducibility.
- Kijun reclaim and MA20 reclaim are very unprofitable on this small sample with the frozen -3/+8 risk and cash rules.
- Global net-return-positivity gate (both periods >0, >=30 completed transactions per period, no blocked PnL) has **zero qualifying strategies**. A lucky positive period must not be represented as a profitable strategy.

## Technical validity and limits

- Ichimoku Tenkan9/Kijun26/SenkouB52, current visible Senkou A/B computed from **26 trading sessions prior**, no future data. Chikou not used. Tests checked a later price bar cannot alter a prior signal.
- Shared 253-session safe-bar/turnover universe, fixed SMA 5/20/60, signal determined at T close only, next open or second open and 5/10 day holding. The T+2 entry is precommitted (never conditions on seeing the T+1 bar).
- Account PnL is not exposure-matched: different strategies enter different stocks on different days with wildly different market exposure. Strong lower loss ≠ superior average alpha.
- Historical stock identity, survivorship, official corporate action/splits/dividends, security delisting payouts, taxes, real opening auction and trigger fills, market impact and corporate-event treatment remain unverified. Thus results are **scenario engineering**, not investable backtest certification.

## Next research hypothesis, still only Ichimoku + SMA

1. Record entry-to-exit holdings and isolated *trade-level normalized* after-cost return aggregates (without exposing ticker/day-level data publicly). Compare the same stock-days and exposure budgets to see whether cloud+SMA confirmation improves the conditional expectation rather than simply trading less.
2. Keep the 5-day -3/+8 fixed bracket as baseline; predeclare additional **early sell** experiment: Ichimoku Kijun close breach or SMA20 close breach, next market open exit, with the same conservative stop. This would directly test *when to sell* based only on these two indicators, avoiding a huge after-the-fact parameter search.
3. Fix issuer/delisting adjustment and actual effective tax/fees before any claim. Keep 2023–2026 independent periods sealed until one fully specified code+data hash is frozen.

**Bottom line:** no profitable buy timing criterion found; strongest research clue is scarce ichi+SMA confluence signals with T+1 5-session holding, but it LOST money in both explored subperiods. Do not place live orders.
