# K-SWING v1.6 — evidence-first, not parameter-mining

## Rationale
v1.5 found negative mean after-cost trade returns across all compared early-exit methods. The previous ~0% portfolio loss was largely a near-zero exposure artifact. A larger indicator search on the same inspected 2019–2022 history would increase data-snooping risk without solving historical execution validity.

## Three independent audit workstreams
1. **Security identity:** daily official ISIN and ordinary-share/market mapping; all historically delisted securities and symbol reuse; source publication vintage at each T-close cutoff.
2. **Corporate actions:** official event record completeness, all price/position adjustments for splits, dividends, mergers and rights; terminal delisting cash flows and suspended securities.
3. **Execution costs:** historically effective-date Korean transaction taxes and fees, T+1 opening auction constraints, participation/market impact and portfolio inventory reconciliation.

These are separate parallel CI audit jobs, not claims that official records were fetched. The automated gate defaults to **BLOCKED** for every missing documentary item, and does not allow real trading or unlock 2026 even when a metadata form is filled. Source metadata is necessary but not sufficient: separate independent reproduction of the underlying evidence is mandatory.

## Historical period caveat
2019–2022 has already been used for iterative research. The repository's v0.9 tested provisional 2023, and v0.4 had 2024–2025 smoke checks. Do not call 2023–2025 pristine independent holdouts. 2026 remains locked pending explicit one-shot preregistration and authorization.

## Success condition
The output of this audit is an **evidence-gap report**, not a profitable strategy. No new alpha or paper-trading is approved. Only after authoritative event- and execution-corrected historical data are reconciled should a new low-complexity hypothesis be preregistered and compared with a frozen negative control, including multiplicity correction.

Existing sources: `official_reconcile_v08.py`, `official_events_v07.py`, `real_execution_v08.py`, and `GO_NO_GO_V09.md`. No API keys, paid subscriptions, live orders, main merge or 2026 market data used.
