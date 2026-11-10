# K-SWING v0.9 — matched incremental alpha and actual portfolio-risk prerequisites

Three independent CI research tracks: Official FSC release/vintage audit, candidate vs baseline matched-sample IC, and 2023 price-print cash + mark-to-market drawdown. **All trades, statistical claims and profits remain provisional until official issuer/rights/delisting/venue fill evidence is provided.**

## Research hypothesis (bounded, exploratory)

Are the 12 previously predefined combinations (especially c08 Bollinger×Parkinson volatility contraction) associated with forward 5/10-session return ranks **after accounting for their baseline ATR7/Parkinson20 volatility inputs**? The key comparison re-evaluates factors on the **same observed future-outcome ticker-days and market dates**. This avoids differences in candidate availability that could mechanically alter sample IC.

Choose the candidate sign and stronger of ATR7/Parkinson20 on 2019–20 discovery ONLY. Then describe the matched candidate-minus-baseline Rank IC and candidate partial rank IC, residualized on both volatility-control ranks, over 2021–22. Both phases have been inspected historically, so **none is a pristine holdout**.

For each candidate/horizon, report aggregate 20-session block-percentile CI, no overstated p-values. Do not claim a positive residual IC means improved executable portfolio profit or statistically independent discovery.

## Risk ledger: why new MDD is necessary

Prior T+1-open/T+H-close cash return may hide interim equity collapse. Ledger now marks **cash + held shares×observed close** each trading session, publishes aggregate maximum drawdown and worst 1-session account change. The moment a held position has an unexplained missing/unsafe bar, whole result, cash return and marked drawdown become unavailable, never a fictional free exit.

Cost assumptions of roundtrip 20/50/100/200 bps still do NOT verify broker tax law, actual fill prices, price limits or slippage. These are engineering price-print sensitivity tests only, based on reused 2023 data.

## Official point-in-time availability control

Historical issuer data `basDt=T` is NOT a T-close input. Conservative schedule is next trading session after 13:00 KST, and actual verified first-publication & vintage timestamps may delay it further. Do not use today-retrieved revised issuer mappings as if originally observed in 2019–22.

Official FSC/KRX history, corporate actions, prior ordinary-share membership and delisted payouts remain UNVERIFIED. The government stock issuance API is subject to a noncommercial license caveat and the necessary authorized data key has not been supplied.

## Hard rules

- v0.9 matched-candidate job uses 2017–22 source to compute 2019–22 signals ONLY; no 2023–2026 records can enter its math.
- Portfolio-risk job uses already inspected 2023 for engineering only, no new winner selection and no 2026 results.
- No mutations outside `research/k_swing/` or `.github/workflows/`.
- GitHub PR stays Draft; main/Streamlit site untouched.
- Before any 'buy today' signal: evidence-qualified historical universe/rights, same-sample incremental performance, selection-adjusted significance, actual fees/taxes/exchange fills, then a single pre-registered untouched 2026 confirmation.
