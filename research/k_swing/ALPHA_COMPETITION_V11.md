# K-SWING v1.1 — profit-first four-arm parallel swing experiment

**Research goal:** maximize observed hypothetical *after-cost account return*, not optimize an accuracy score. Any candidate must pass conservative data-integrity gates before investment relevance is even considered.

## Academic hypotheses (not claims of profits in Korea)

- George and Hwang (2004), The 52-Week High and Momentum Investing, Journal of Finance. https://doi.org/10.1111/j.1540-6261.2004.00695.x
- Jegadeesh (1990), Evidence of Predictable Behavior of Security Returns, Journal of Finance. https://doi.org/10.1111/j.1540-6261.1990.tb05110.x
- Short-Term Reversal and Short-Term Momentum in the Korean Stock Markets (2023). https://www.kci.go.kr/kciportal/landing/article.kci?arti_id=ART002987582
- Barroso and Santa-Clara (2015), Momentum Has Its Moments. https://www.sciencedirect.com/science/article/pii/S0304405X14002566 — future risk-scaling investigation, NOT part of initial frozen rules.

No paper's out-of-sample result is claimed to transfer to our 5–10-day Korean-stock simulation. Candidate thresholds are first-principles research hypotheses and not fitted optima.

## Four parallel research jobs

1. momentum52: T close at least 95% of prior 252-session maximum high; 60-session return at least +12%, price above 20-session SMA, T volume at least 1.2 times prior 20-session average.
2. reversal3: past 3-session return at most -7% with past 60-session return >= +5%, price at least 85% of current 60-session SMA, and T volume at least 1.3 times prior 20-session average.
3. vcr_trend: v1.0 pre-breakout compression + T close 20-session high break + volume 1.8x, plus past 60-session gain >= +10% and close at least 80% of previous 252-session high.
4. vcr_control: v1.0 VCR rule, within the same eligibility universe as the new hypotheses.

At T: all four require 253 contiguous SAFE exchange-session bars, close >= 1,000 KRW, T turnover and previous 20-session mean turnover each >= KRW 3bn. No date-T signal uses dates after T. No unseen corporate actions are assumed tradable.

## Profit-oriented backtest protocol

- Stock source and audit: same screened KOSPI/KOSDAQ derived OHLCV 2017–2022. Deterministic sha256(code) modulo-16 sample; not the full market, so it cannot establish market-wide investable performance.
- Independent discovery signals 2019-01-01 to 2020-12-15 and internal signals 2021-01-01 to 2022-12-15. Both are previously inspected research periods, and neither is pristine independent confirmation.
- Each research arm and period is evaluated at 5 and 10 sessions maximum holding. T close decision, T+1 opening-print purchase, model cash 100 million KRW, max 5 million KRW per ticket, 10 simultaneous positions, choose up to 10 signals daily with no profitable after-the-fact replacement.
- Hypothetical roundtrip cost: 50 bps, stop -3%, target +8%. Overnight gaps use opening print where available. When unknown same-day low/high ordering hits both stop and target, assume stop first. This is not verified venue execution.
- Account NAV marked each close and MDD recorded; missing/suspected-action held bars invalidate any aggregate PnL claim. All losses must be reported.
- Precommitted positive-return eligibility: **both** discovery and internal periods positive after the hypothetical cost, at least 30 completed trades in EACH, and neither has an unresolved exit. If no candidate meets this threshold, report NO PROFITABLE CANDIDATE. For qualified candidates, the largest positive return is the PRIMARY research sorting metric, with MDD and exposure diagnostics secondarily. This is a research gate, not live permission.
- Four jobs run as GitHub Actions matrix **in parallel**; each job independently downloads private inputs and publishes ONLY aggregate results. The per-stock bars and fills are purged from the runner.

## What we still cannot honestly claim

We have not established official historical ISIN/ordinary share and delisted security mapping, corporate-action-adjusted OHLCV, last-trade delisting payouts, historically effective brokerage tax schedules, or realistic order book execution and market price limits. Account risk and investment return remain unverified.

Stock-level signal opportunities and average cash exposure still differ between strategies despite the common eligibility universe, so terminal account returns are NOT causal proof of a superior alpha signal. Follow-up work should compare matched stock-day entry cohorts, normalized invested-notional returns, actual trade-level success probabilities and regime robustness.

Do NOT use previously inspected 2023 or untouched 2024/2025/2026 data for any selection in this task. The final 2026 confirmation is sealed until a single fixed rule and data contract have been preregistered. Do NOT place brokerage orders or merge the draft into main.
