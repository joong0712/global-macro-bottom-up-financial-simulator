# K-SWING v0.9 — Go / No-Go checklist for a future trade rule

**Research decision status now: NO-GO for live-money orders, no confirmed alpha.**

## Critical provenance

- Only training 2019–20 vs internal 2021–22 was used for v0.9 candidate/baseline incremental IC. All years have previously been inspected in other versions; **internal validation is NOT an independent fresh holdout**.
- The provisional v0.9 cash/mark-to-market risk tests use already inspected 2023; price prints are not venue-executable fills.
- No signal-selection use of 2024, 2025, or 2026 in v0.9. The 2026 final confirmation dataset remains locked.

## Evidence necessary BEFORE selecting a finalist

1. **Authoritative security identity:** date-specific FSC/KRX ISIN, ordinary share type, correct historical market/sector, delisted security universe and ticker reuse. Matching `basDt` to T does not imply public availability by T close.
2. **Authoritative corporate actions:** all relevant splits, consolidation, stock dividend, rights issues, merger and last trading/delist payouts, adjusted OHLCV and holdings. Suspicious marcap discontinuities are NOT official confirmations.
3. **Historically correct public time and vintage:** event actually disclosed by signal cutoff; FSC daily issuer snapshot update as early as next business day 13:00 KST, not same-day T-close. If historical vintage is not independently verified, fail closed.
4. **Execution and cost validation:** actual T+1 opening auction constraints, price limits, suspensions, minimum lots, enough cash, position overlap, fees/levies and effective dates, multi-year slippage and participation restrictions. Unrealized mark-to-market MDD must be tracked, never just end-of-year cash.
5. **Incremental value beyond baseline:** predeclare candidate formulas and compare with baseline on identical day/security/forward-label sample; require both paired IC improvement and incremental risk-adjusted cash performance, not a nominal Rank IC or posthoc K-only win.
6. **Statistical dependence:** daily 5/10-session forward returns overlap, factor expressions are correlated (including exact sign mirrors); report block dependence, uncertainty intervals, annual/market regime consistency and multiplicity-adjusted tests. Do not use reused 2023 to choose the best formula/K/horizon.

## Rules before one-time independent confirmation

- Freeze exact candidate formula, sign, universe, market/sector filters, signal timestamp, order eligibility, K, risk caps, fee/tax regime, entry, exit, max holding and cash accounting from historical training only.
- Publish frozen configuration hash and replay code before opening 2026 one single time.
- Report failures, no-fill and unresolved delisting scenarios with no silent substitutions.
- Only after a robust one-time confirmation, conduct paper-trading. No actual brokerage orders in this repository at present.

## Scope boundaries

Workflow contains no official account credential, no brokerage login, no hidden cloud execution, and no production web modifications. This checklist is a decision gate, not a claim that the underlying evidence exists.
