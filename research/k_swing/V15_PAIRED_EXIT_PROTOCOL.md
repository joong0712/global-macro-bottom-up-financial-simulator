# K-SWING v1.5 — same-entry paired exit evaluation and calendar block uncertainty

**NO VERIFIED POSITIVE ALPHA.** This is a diagnostic under historical (reused) data. Do not trade, do not train on 2023–2026, and do not merge into main.

## The central problem being tested

v1.3 / v1.4 showed the Ichimoku + SMA entry cohort had much smaller total-account losses than plain Golden Cross or Kijun re-entry. But the strategy held far fewer positions and much lower average stock exposure. Negative smaller PnL cannot establish a stronger signal, and buying a stock on different dates does not produce a valid paired comparison.

Here we fix the exact historical **T-close stock/date entry events and the T+1 opening price** for each of two frozen, previously used entry families: Ichimoku-cloud+MA alignment and VCR+trend. Four alternative exits are all run on the same exact matched trades, with no concurrent account capital limits. They are:

1. Baseline: -3% intraday stop, +8% take profit, otherwise 5- or 10-held-session close.
2. Kijun26: same stop/take, plus a T-close Kijun26 bearish breach executed at T+1 open.
3. SMA20: same stop/take, plus T-close below SMA20 -> T+1 open sell.
4. Either: same stop/take, plus T-close below either Kijun/SMA20 -> T+1 open sell.

No future price is an input to any entry/exit decision. Missing held bars invalidate the whole comparison, never silently drop unfavourable trades. Missing entry print means the trade was never entered and is skipped *before* outcomes, identically for every policy.

## One matched-trade estimand — NOT portfolio PnL

- Per-ticket after-cost return is (exit/entry) times ((1-half fee)/(1+half fee)) minus 1. Roundtrip costs stressed at 50, 100, and 200 basis points, without re-optimizing parameters.
- For each exit candidate, calculate mean net matched trade return, signed improvement versus the same-event baseline, fraction of winning trades, and mean held sessions.
- Market-wide events and correlated stock signals mean trades are NOT IID. Non-overlapping **20 exchange-session calendar blocks** retain cross-stock same-date dependence. Resample those calendar blocks with replacement 2,000 times (fixed RNG seed), and report an exploratory percentile 95% CI for the mean *paired exit advantage*.
- Baseline / early exit comparison uses the same date-stock set and initial ticket. It ignores cash available, share lot rounding and overlapping positions, so it is an **isolated trade-quality diagnostic** and must NOT be called executable portfolio return.
- The block CI is an uncertainty diagnostic only; it is NOT adjusted for many v1.0–v1.4 trials, different trial horizons, strategy selection bias or previously inspected history. It therefore cannot certify generalization.

## Parallel and validation

Two CI matrix jobs: one for Ichimoku+MA, one for VCR+trend. Each evaluates both previously explored 2019–20 and 2021–22 periods and 5/10-session max holding. All three early exits are compared against a fixed baseline at 50, 100, and 200bp in aggregate. A separate regression test job checks stop-before-take, next-open exit after close, no future leakage, missing-held blocking, exact one-ticket baseline reconciliation, bootstrap deterministic behaviour.

Common KOSPI/KOSDAQ 2017–22 screened OHLCV and 1/16 deterministic ticker sample, no 2023–2026 loading. At the original signal time T require previous 253 safe exchange-session bars, positive price/liquidity (from v1.3 candidate builder). Aggregate artifacts only; never publish ticker/date/individual fill evidence.

## Strict candidate gate

To qualify even as a *further study hypothesis*, both already inspected periods must each have >=30 matched safe trades, positive mean net ticket return with 50bp AND 100bp costs, and strictly positive 95% block-CI lower bound for matched improvement at 50bp. If this does not occur, **NO PROFITABLE MATCHED EXIT ADVANTAGE**. Even passing this gate cannot be called verified profit: no fresh holdout, market completion, corporate actions/delisting identity, actual taxes, real exchange fills, price impact or capital-constrained portfolio consistency.

Do not optimize after seeing negative data; write down the failure, preserve the full outcome matrix, and move to **source-data provenance and actual execution** before testing any new family. No real orders.

## Academic safeguards

- Sullivan, Timmermann & White (1999), Data-Snooping, Technical Trading Rule Performance, and the Bootstrap: https://doi.org/10.1111/0022-1082.00163
- White (2000), A Reality Check for Data Snooping: https://doi.org/10.1111/1468-0262.00152
- Bailey et al. (2017), The Probability of Backtest Overfitting: https://escholarship.org/uc/item/4w1110bb
- The impact of data snooping on technical analysis: evidence from Asian stock markets: https://www.sciencedirect.com/science/article/pii/S1049007809000682

These papers motivate methodological safeguards. They are not evidence of an alpha signal in this sampled Korean swing strategy.
