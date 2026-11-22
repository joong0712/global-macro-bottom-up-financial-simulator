# K-SWING v1.4 — Paper-grounded Ichimoku / MA early-exit experiments

Research-only. Goal is positive *after-cost, realistic cash account returns*, not a posthoc winning chart. No 2023–2026 input or broker orders.

## Eight preregistered, parallel exit policies

We freeze two entry families, already examined in v1.3:
- ichi_ma_confirm: upper visible Ichimoku cloud break + SMA20>SMA60 and close>SMA20; buy the following session open.
- vcr_trend_control: original VCR compression, 60-session return +10% and >=80% of prior 252-session high; buy the following session open.

For each entry family, compare four predeclared exits:
1. baseline: only intraday -3% stop / +8% take or 5-/10-session maximum holding period.
2. kijun_break: same bracket, but on **T close below Kijun 26**, sell at **T+1 session open**.
3. sma20_break: same bracket, but on **T close below SMA20**, sell at **T+1 session open**.
4. either_break: same bracket; if T close below Kijun 26 OR SMA20, exit at T+1 open.

IMPORTANT: Stop or take triggered during date T takes priority over any indicator rule at T close. If both stop and take touch an OHLC bar, stop executes first. A close-based indicator signal can never liquidate at the same day's close because its final value was not yet observed before market close. An overnight gap uses the next actual daily opening print, NOT a synthetic profitable price.

For each of 8 parallel jobs, evaluate 2 reused historical periods x 2 max holding periods (5 or 10 sessions, including entry date): 32 distinct account scenarios. The original T+1 broker entry, -3/+8 bracket, cash and baseline assumptions are unchanged. Unit tests check baseline parity against the previous v1.3 simulator, no future information, and unsafe-held-bar fail closed.

## PnL and exposure assumptions

- Korean securities screened from 2017–2022 KOSPI/KOSDAQ per prior project quality audit. Deterministic SHA-256 ticker modulo 16 (~166 stocks), 253 clean sessions for entry signals. 2019-01-01 to 2020-12-15 and 2021-01-01 to 2022-12-15 signal windows. These periods are **already inspected by v1.0–v1.3**, not independent test windows.
- Initial account KRW 100m, target ticket KRW 5m, up to 10 concurrent holdings, max top 10 ranked signals/day, 50 basis points hypothetical roundtrip cost.
- Daily cash + marked share NAV and MDD, as well as mean invested-capital fraction and mean closed trade net percentage, are published **in aggregate only**.
- Any unresolved held session or suspected issuer action blocks all account PnL instead of excluding trades.
- No actual historical full issuer registry, splits, delistings, effective taxes, opening auction/trigger fills or market impact guaranteed. A positive hypothetical number is NOT investable alpha.

## Explicit acceptance gate before a research candidate

A rule must have >=30 completed trades and **positive after-cost portfolio return in each predeclared 2019–20 and 2021–22 account period**, with no unknown held bar. Because two periods are reused and candidate list itself comes from repeated research, this is a DISCOVERY gate only, not statistically independent profitability evidence.

Compare against the frozen no-early-exit baseline with the same entry signals, holding period, capital and costs. Report both account returns AND mean trade net return AND mean daily invested fraction; avoid declaring a winner solely because the strategy spent less time in risky assets. All losing or blocked arms remain visible. Higher return without similar exposure is not definitive alpha.

If no arm passes, report NO PROFITABLE EXIT RULE. Do not silently alter historical loss-making rules, select based on 2023–2026 data, or place any real money orders.

## Research literature and rationale

- Sullivan, Timmermann and White (1999), Data-Snooping, Technical Trading Rule Performance, and the Bootstrap, Journal of Finance: https://doi.org/10.1111/0022-1082.00163 . Many variants can look profitable due to selection bias; independent confirmation and multiple-testing control are necessary.
- George and Hwang (2004), The 52-Week High and Momentum Investing, Journal of Finance: https://doi.org/10.1111/j.1540-6261.2004.00695.x . Motivates certain existing trend signals, not the exit methods or their presumed profits.
- Moskowitz, Ooi and Pedersen (2012), Time Series Momentum, Journal of Financial Economics: https://doi.org/10.1016/j.jfineco.2011.11.003 . Broad cross-asset time-series phenomenon, not evidence for the specific Korean stocks / 5-day horizon here.
- Trading to Stops (2015), SIAM Journal on Financial Mathematics: https://doi.org/10.1137/130911706 . A formal trading-stop approach; our fixed bracket remains an unoptimized benchmark.
- Technical Ichimoku formula: https://chartschool.stockcharts.com/table-of-contents/technical-indicators-and-overlays/technical-overlays/ichimoku-cloud . At T use current Tenkan/Kijun, but a projected cloud visually at T is based on values from T-26, never future T+26. We do NOT use a future Chikou signal.

Follow-up priority if this trial fails: repair company-action and historical-universe provenance, validate genuine fills/taxes, then consider time-series momentum or convex risk stops **as new preregistered hypotheses**, not tweak until training-period gains appear.
