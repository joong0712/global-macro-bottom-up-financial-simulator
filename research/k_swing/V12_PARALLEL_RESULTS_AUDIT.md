# K-SWING v1.2 — parallel-profit experiment audit

## Final verdict: NO-GO — no demonstrated profitable Korean 5–10-day swing alpha

- Latest completed all-jobs successful GitHub Actions: https://github.com/joong0712/global-macro-bottom-up-financial-simulator/actions/runs/45053936608
- Earlier run: https://github.com/joong0712/global-macro-bottom-up-financial-simulator/actions/runs/45053573755 . Failed only because the ML runner omitted scikit-learn. Explicit scikit-learn installation and preflight were added before the successful rerun.
- Evaluated **already-inspected** 2021-01-01 through 2022-12-15 development sample of 166 deterministic 1/16-hash stocks; no 2023–2026 input opened.
- All 2017–2022 inputs passed historical calendar audit. But issuer identity, security actions, delisting handling and real KRX execution costs are NOT certified.
- Training period for LightGBM ends 2020-12-01, and all training labels mature by 2020-12-15. 2021–2022 evaluation outcomes were not trained as labels.

## Track A: LightGBM net bracket-return ranker

| Horizon | Matured training examples | Positive predicted signals | Simulated closed trades | Unresolved unsafe held bars | Account net return | MDD |
|---|---:|---:|---:|---:|---|---|
| 5 sessions | 10,794 | 3,125 | 1,612 | 2 | **BLOCKED** | **BLOCKED** |
| 10 sessions | 10,791 | 3,857 | 1,463 | 2 | **BLOCKED** | **BLOCKED** |

The model completed training and prediction, but the existing conservative cash simulator encountered two unresolved held-stock bars in each scenario. It correctly returned null instead of any PnL. **No numeric portfolio return is permitted.** Removing unverified trades after seeing outcomes would cause ex-post selection bias.

Exit reason counts among *resolved* trades only, not PnL: for 5 sessions intraday stop 951, stop gap 81, intraday take 317, take gap 19, time close 244. For 10 sessions intraday stop 921, stop gap 95, intraday take 334, take gap 31, time close 82. High stop concentration is a negative diagnostic, not a valid overall strategy profitability claim.

Artifacts: kswing-v12-ranker-aggregate-only, artifact ID 14766414674.

## Track B: fixed as-of market-regime switching

| Horizon | Completed hypothetical trades | Cash portfolio net return | MDD | Status |
|---|---:|---:|---:|---|
| 5 sessions | 89 | -4.8063% | -6.8324% | Hypothetical OHLC only |
| 10 sessions | 89 | -5.0506% | -7.2811% | Hypothetical OHLC only |

Regime counts: sideways 388, bear 82, bull 14 observation dates; signal opportunities 94, resulting 89 closed trades. The 5-day scenario stopped out intraday 63 times, had 16 intraday takes, 1 take-gap and 9 timed exits. The 10-day scenario had 69 intraday stops, 1 stop gap, 18 intraday takes and 1 take gap. Neither scenario was profitable.

Artifacts: kswing-v12-regime-aggregate-only, artifact ID 14766473830. The earlier matching first-run artifact is 14766715682.

## Required decisions

- v1.2 did NOT pass its profit-first objective; do not call either track best or deploy capital. Neither track independently validated a profitable alpha.
- Track A is **unknown return**, not 0% return and not an implicit win; it has a large 1,600+ trade exposure vs regime's 89 trades. The two account equity returns (even if A were resolved) would not establish causal superior trade-level quality.
- Before any ML tuning, resolve the **2 unsafe held intervals per horizon** against official historical corporate actions / listing / delisting records and assure there is a well-defined executable liquidation treatment. The diagnosis should stay in private run logs; never leak security-level signals in public artifacts.
- After correctness, compare against v1.1 VCR+trend control on **matched dates and normalized invested-notional** rather than just total cash NAV; implement actual effective Korean taxes, fees, fills and transaction constraints.
- Keep previously inspected 2023 and untouched 2024-2026 samples locked for predeclared one-shot testing. No automatic PR merge, no broker orders.

**Outcome:** Profit-first algorithm development produced a valid negative regime result and an appropriately BLOCKED ML result. Integrity gates worked; a credible profit-maximizing investment model has not yet been demonstrated.
