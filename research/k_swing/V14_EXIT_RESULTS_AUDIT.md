# K-SWING v1.4 — Ichimoku/SMA early-exit preliminary results

## Verdict: NO-GO. All 32 simulated after-cost cash returns are nonpositive.

- First fully successful all-nine-jobs run: https://github.com/joong0712/global-macro-bottom-up-financial-simulator/actions/runs/45055875094
- 8 strategy-entry/exit arms, each with 2019–20 / 2021–22 periods and max 5/10 held sessions = **32 total simulated account scenarios**. No rule passed net return >0 in BOTH periods.
- The prior v1.3 baseline 5/10-day returns reproduced to 0.01 percentage point with the new accounting engine.
- Brokerage, actual fills, official corporate actions/delisting, and effective historic taxes remain unverified. These are not investable PnL statistics.
- CORRECTED EXPOSURE VALIDATION: [all 9 jobs successful after the exposure-window correction](https://github.com/joong0712/global-macro-bottom-up-financial-simulator/actions/runs/45056246696). Inspected all 8 new aggregate JSON artifacts; account PnL, MDD and mean trade returns remained unchanged while mean invested fractions now apply to each experiment's signal period plus exit buffer. These historical daily means quantify *time in positions*, not verified actual capital execution.
- No 2023–2026 holdout was opened.


## Corrected invested-capital exposure (verified rerun)

Selected baseline scenarios from GitHub Actions #45056246696. **Percentages here are percentages of the cash account, NOT 0.568 = 56.8%.**

| Entry | H sessions | Period | Account net return | Mean invested fraction | Mean net closed trade |
|---|---:|---|---:|---:|---:|
| Ichimoku + SMA | 5 | 2019-20 | -0.393% | 0.568% | -0.225% |
| Ichimoku + SMA | 5 | 2021-22 | -1.062% | 0.491% | -0.712% |
| Ichimoku + SMA | 10 | 2019-20 | -0.278% | 0.807% | -0.162% |
| Ichimoku + SMA | 10 | 2021-22 | -1.112% | 0.559% | -0.773% |
| VCR + trend | 5 | 2019-20 | -3.566% | 0.127% | -2.389% |
| VCR + trend | 5 | 2021-22 | -0.039% | 0.459% | -0.015% |
| VCR + trend | 10 | 2019-20 | -3.566% | 0.126% | -2.389% |
| VCR + trend | 10 | 2021-22 | -0.390% | 0.625% | -0.206% |

Critically, both entry methods invest **far less than 1% of capital on a typical calendar day**; near-flat NAV cannot be interpreted as low-risk positive alpha. Their per-trade means are negative in the selected periods. These are preliminary engineering estimates, not official trade execution records.

## All 32 hypothetical net portfolio returns (%)

Independent simulated accounts per period; never sum 2019–20 and 2021–22 as if a common uninterrupted portfolio.

| Entry | Exit | Hold | 2019–20 net | 2021–22 net | Trades 2019–20 / 2021–22 |
|---|---|---:|---:|---:|---:|
| Ichimoku+SMA | baseline | 5 | -0.393 | -1.062 | 35 / 30 |
| Ichimoku+SMA | baseline | 10 | -0.278 | -1.112 | 35 / 29 |
| Ichimoku+SMA | Kijun26 break | 5 | -0.604 | -1.353 | 35 / 30 |
| Ichimoku+SMA | Kijun26 break | 10 | -0.415 | -1.363 | 35 / 30 |
| Ichimoku+SMA | SMA20 break | 5 | -0.659 | -1.411 | 36 / 30 |
| Ichimoku+SMA | SMA20 break | 10 | -0.585 | -1.421 | 36 / 30 |
| Ichimoku+SMA | either break | 5 | -0.870 | -1.367 | 36 / 30 |
| Ichimoku+SMA | either break | 10 | -0.721 | -1.377 | 36 / 30 |
| VCR+trend | baseline | 5 | -3.566 | -0.039 | 30 / 37 |
| VCR+trend | baseline | 10 | -3.566 | -0.390 | 30 / 37 |
| VCR+trend | Kijun26 break | 5 | -3.566 | -0.039 | 30 / 37 |
| VCR+trend | Kijun26 break | 10 | -3.566 | -0.261 | 30 / 37 |
| VCR+trend | SMA20 break | 5 | -3.566 | -0.039 | 30 / 37 |
| VCR+trend | SMA20 break | 10 | -3.566 | -0.390 | 30 / 37 |
| VCR+trend | either break | 5 | -3.566 | -0.039 | 30 / 37 |
| VCR+trend | either break | 10 | -3.566 | -0.261 | 30 / 37 |

Each listed period/hold/entry-exit corresponds to one scenario; there are 16 rows x 2 historical periods = 32 account returns.

## What made the difference?

- Ichimoku cloud breakout + SMA positive alignment remains extremely infrequent and loss-making. Its **5-session baseline** had hypothetical mean after-cost trade return -0.225% (2019–20) and -0.712% (2021–22). The Kijun26 exit became -0.346% and -0.908% respectively; combining Kijun/SMA became -0.485% and -0.917%. This does not establish a useful early-sell advantage.
- On the *2019–20 VCR+trend account*, not a single T-close Kijun/SMA trigger executed while the position was still held before a fixed bracket/time exit. All four exit policies show identical -3.566% losses.
- On *2021–22 VCR+trend*, the 5-day stop/time baseline remains -0.039% and indicator exits never occur before bracket termination. For the 10-day strategy, **one** Kijun/either exit improves -0.390% to -0.261%, not enough to become profitable.
- The ability to avoid trading is NOT evidence of per-trade alpha. Different entry families have wildly different opportunity counts and active capital; use corrected measured exposure and mean trade net returns in any head-to-head comparison.
- These samples and signals were repeatedly inspected in previous v1.0–v1.3 cycles. The best-looking historical variant suffers selection bias. Do not treat this as new independent confirmation.

## Paper and next research priorities

The best next steps are NOT an unconstrained search to force a positive historical number. Identify actual issuer actions/delistings and trading taxes, build normalized matched-trade/holding exposures, quantify uncertainty with a bootstrap that respects shared calendar blocks, and only then preregister a genuinely new hypothesis on sealed data.

- Sullivan, Timmermann & White (1999), data-snooping and technical rule reality checks: https://doi.org/10.1111/0022-1082.00163
- Imkeller & Rogers (2014), Trading to Stops, includes trade costs in a stopping-rule framework: https://doi.org/10.1137/130911706
- Moskowitz, Ooi & Pedersen (2012), time-series momentum across other asset classes; offers a possible distinct future hypothesis, not an established Korean 5-day edge: https://doi.org/10.1016/j.jfineco.2011.11.003

**NO LIVE TRADE, no opening of 2023–2026 independent data, no merging Draft PR to production.**
