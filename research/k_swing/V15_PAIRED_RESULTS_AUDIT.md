# K-SWING v1.5 — matched-opportunity exits, cost stress and block-bootstrap audit

## Final verdict: NO-GO — no positive mean matched trade return in both explored historical periods

**Verified all three CI jobs completed successfully:** https://github.com/joong0712/global-macro-bottom-up-financial-simulator/actions/runs/45056842269
- Causal/regression tests: SUCCESS.
- Independent runs: paired-ichi_ma_confirm SUCCESS, paired-vcr_trend_control SUCCESS.
- Exact aggregate results: GitHub Actions artifact IDs **14767842338** (Ichimoku+SMA) and **14767238886** (VCR+trend). Source OHLCV, ticker/day traces and individual fills never published.
- 2017–2022 historical input; sampled 166 securities, 253 safe exchange sessions, T signal -> T+1 open. 2023–2026 NOT read by this workflow; across the whole research project, 2023 was previously examined in v0.9 and 2024–2025 partially smoke-tested in v0.4. Only the strictly protected 2026 confirmation remains designated as single-use after exact precommitment.
- All paired scenario data statuses were PAIRED_TRADE_DIAGNOSTIC_NOT_CAPITAL_PORTFOLIO. No held-stock unresolved/blocking errors in the matched sample. This does NOT officially verify issuer events, real fills or true fee/tax schedules.

## Paired trade returns at assumed roundtrip 50bps

Figures are percent net return **per matched isolated trade**, not 100m KRW account returns. The SAME stock/date/T+1 opening print is used across each row's baseline and exit variants.

| Entry | Historical split | Maximum H | Matched trades | Baseline | Kijun exit | SMA20 exit | Either exit |
|---|---|---:|---:|---:|---:|---:|---:|
| Ichimoku+SMA | 2019-20 | 5 | 37 | -0.233% | -0.347% | -0.451% | -0.566% |
| Ichimoku+SMA | 2019-20 | 10 | 37 | -0.078% | -0.152% | -0.413% | -0.487% |
| Ichimoku+SMA | 2021-22 | 5 | 31 | -0.801% | -0.991% | -1.028% | -1.000% |
| Ichimoku+SMA | 2021-22 | 10 | 31 | -0.948% | -0.997% | -1.035% | -1.006% |
| VCR+trend | 2019-20 | 5 | 32 | -2.116% | -2.116% | -2.116% | -2.116% |
| VCR+trend | 2019-20 | 10 | 32 | -2.116% | -2.116% | -2.116% | -2.116% |
| VCR+trend | 2021-22 | 5 | 38 | -0.107% | -0.107% | -0.107% | -0.107% |
| VCR+trend | 2021-22 | 10 | 38 | -0.292% | -0.224% | -0.292% | -0.224% |

**No baseline or early exit produces positive mean 50bps net return consistently in both periods.** All 6 early exit/holding candidate diagnostic gates failed (per frozen entry family). Under a larger 100bps roundtrip trading cost, every shown candidate remains negative (see aggregate JSON).

## Statistical differences: what was actually learned

- Ichimoku+SMA **5 sessions**: Kijun exit worsened mean matched return by -0.114 percentage point (2019–20) and -0.189 percentage point (2021–22). The 95% 20-market-session block CIs for matched difference were **[-0.373%, 0.000%]** and **[-0.901%, +0.174%]**, respectively. Neither supports positive expected improvement.
- Ichimoku+SMA **5 sessions** SMA20 exit worsened results by -0.218 and -0.227 percentage points, with 95% block CIs **[-0.799%, +0.105%]** / **[-1.084%, +0.161%]**.
- VCR+trend 2019–20: early exit produced EXACTLY 0.000 percentage-point improvement across all rules, both 5 and 10 sessions; no active indicator exits before bracket close.
- VCR+trend 2021–22 **10 sessions**: Kijun/either improved mean net trade by just +0.068 percentage point, with respective block CIs **[0.000%, +0.168%]** and **[0.000%, +0.172%]**, both including zero. Variant mean stays **-0.224%**. This is not convincing alpha, and the earlier 2019–20 period was -2.116%.
- The CI is 20-calendar-session block resampling of *matched exits* (2000 bootstrap replications) and does not correct for trying many strategies historically. It does not prove independent generalization. The sample sizes 31–38 trades per period are thin.

## Why this matters for the profit-first research objective

These results resolve a central ambiguity of v1.3–v1.4: lower negative account NAV alone was partly due to **lower average capital invested**, typically under 1% of the original account. Even after directly matching same entry opportunities and computing **trade-level return per invested ticket**, mean returns remain negative. So it would be misleading to promote Ichimoku+SMA as a "profitable rule".

The new separate-trade experiment intentionally does not model capital overlap, broker share rounding, cash caps, trade competition or portfolio MDD. It is only a **diagnostic** of exit rule choice. It is not a replacement for a full exchange-executable portfolio simulation.

## Next actions before developing another alpha candidate

1. Prioritize **historical security provenance and corporate actions** (date-specific official ISIN, market and share type, splits/consolidation, last delisting prints). Existing quarantined bars are not sufficient official reconciliation.
2. Confirm Korean **effective-date trading tax**, brokerage commission, auction mechanics, price limits, suspensions, corporate cash events, and security liquidity, then reconstruct a realistic ledger. KOSPI and KOSDAQ taxes changed during 2019–22; the current fixed 50bp fee is a stress assumption, not a historical tax schedule.
3. If a wholly NEW strategy hypothesis is added, pre-register its universe, ranking, entry, stop, hold time and costs before evaluations. Use negative controls and a dependence-aware, multiple-testing-adjusted test (e.g., White's Reality Check / Hansen SPA); 2019–22 cannot be rebranded as a pristine validation set.
4. A final investor-relevant conclusion would need independent event-corrected portfolio tests and **one** truly locked confirmation evaluation, not continued parameter tweaking on the same prices.

Sources:
- Sullivan, Timmermann, White (1999), technical trading data snooping, https://doi.org/10.1111/0022-1082.00163
- White (2000), A Reality Check for Data Snooping, https://doi.org/10.1111/1468-0262.00152
- Bailey et al. (2017), Probability of Backtest Overfitting, https://escholarship.org/uc/item/4w1110bb
- Asian market rule data snooping, https://www.sciencedirect.com/science/article/pii/S1049007809000682

**FINAL v1.5 RESEARCH DECISION: NO-GO. No real brokerage orders, no automatic merge to main, and do not unlock 2026.**
