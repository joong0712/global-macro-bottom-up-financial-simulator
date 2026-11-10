# K-SWING v0.9 — provisional cash/marked-position max drawdown results

## Execution provenance

- GitHub Actions [#42897397840](https://github.com/joong0712/global-macro-bottom-up-financial-simulator/actions/runs/42897397840): **all three independent jobs succeeded** (official timestamp+vintage policy, incremental factor IC, real-bar portfolio risk).
- [Aggregate cash/margin/MDD artifact](https://github.com/joong0712/global-macro-bottom-up-financial-simulator/actions/runs/42897397840/artifacts/13801287564), source: 2017–2023 FinanceData/marcap pinned snapshot. 2023 was already inspected; no 2026 records read.
- 176 historical sample ticker codes, 245 source 2023 signal dates. **32 pre-registered** hypothetical cost × factor × horizon × K scenarios.
- Cash-and-positions ledger uses nominal historical T+1 **opening print**, T+5/T+10 **closing print** and now daily **cash + held stock × closing print** mark-to-market equity for drawdown. No actual exchange execution match.

## Representative Parkinson volatility, Top-10, ten-session holding

| Hypothetical roundtrip cost | Simulated end-of-year cash return on 100m KRW | Max close-to-close marked equity drawdown | Worst marked session NAV change | Completed theoretical trades |
|---|---:|---:|---:|---:|
| 20bp | **+5.0716%** | -3.7835% | -1.3523% | 113 |
| 50bp | **+3.3766%** | -3.8523% | -1.3594% | 113 |
| 100bp | **+0.5516%** | -4.5430% | -1.3713% | 113 |
| 200bp | **-5.0984%** | -8.3464% | -1.3958% | 113 |

**Interpretation:** marked equity may have material temporary losses not visible in completed-trade averages. Even with positive simulated net cash, marked daily drawdown, overnight/intraday movement and tax/fill uncertainty could invalidate realistic trading performance.

### Another case at 50bps — two baseline indicators

| Factor | H | K | Simulated full-period cash return | Marked MDD | Completed hypothetical trades |
|---|---:|---:|---:|---:|
| ATR Wilder7 | 5 | 10 | +0.61% | -3.59% | 170 |
| ATR Wilder7 | 10 | 10 | +2.70% | -3.64% | 111 |
| Parkinson20 | 5 | 10 | -1.05% | -4.73% | 175 |
| Parkinson20 | 10 | 10 | +3.38% | -3.85% | 113 |

Changing holding horizon K based on already inspected 2023 would be post-hoc overfitting. **No evidence these signals are reliably profitable in new markets.**

## Major blockers remain

- **All 32 scenarios had 0 flagged unresolved exits in the observed, sampled price files**. These are not official corporate-action, ceased-security or delisting audits; a previously delisted stock may be outside the observed sample, and raw marcap splits may be wrong.
- Cost values are simple *assumed total roundtrip bp deductions*; do not claim actual Korean securities taxes, commission, slippage, price limits, auction fills or market-impact constraints have been audited.
- Daily end-of-session mark-to-market MDD **does not include intraday drawdowns** or any unobserved suspended/delisted shares.
- Currency accounting of fixed tickets/positions is a prototype, not verified margin/risk-engine behavior. No true PIT official ordinary-share universe, listed-sector or release-vintage completeness.
- This simulation uses 2023, an already-inspected exploration year, and CANNOT be used to select optimal horizon or K as an independently validated strategy.
- **The separate v0.9 candidate-vs-ATR/Parkinson study on 2019–22 found 0 / 24 new candidate/horizon pairs with positive mean matched incremental Rank IC in the internal period.** [See negative report](https://github.com/joong0712/global-macro-bottom-up-financial-simulator/blob/research/k-swing-v09/research/k_swing/reports/MATCHED_INCREMENTAL_CANDIDATE_V09.md).

## Next go/no-go decision

**NO-GO for live-money rule** until licensed/authenticated issuer identity and corporate action/delisted payout history, actual dates/taxes/filled order checks, true independent preregistered confirmation, and evidence of improvement over baseline. New candidate generation should seek independent explanatory mechanisms rather than reparameterized volatility.

Original Streamlit web and main unchanged; 2026 confirmation remained locked.
