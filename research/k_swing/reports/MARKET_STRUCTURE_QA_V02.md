# K-SWING v0.2 — historical-data structure and corporate-action candidate audit

## Run provenance

- Run (successful): https://github.com/joong0712/global-macro-bottom-up-financial-simulator/actions/runs/42858791358
- Aggregate results artifact (7-day retention): https://github.com/joong0712/global-macro-bottom-up-financial-simulator/actions/runs/42858791358/artifacts/13784722469
- Base source: https://github.com/FinanceData/marcap @ 94c138df4bf7376be8d28f979edb14020e2a547a
- Covered data: 2017-01-02 through 2026-11-06 (2026 is incomplete)
- Source market records kept after OHLCV normalization: **5,639,753**
- Automated tests passed: **21** (40 nonfatal warnings; follow up if versions change)

## Trading session verification

- Observed market session dates: **2,413**
- Third-party exchange_calendars XKRX sessions: **2,415**
- Reference-only dates: 2026-06-03 and 2026-07-17
- Both were KRX-announced 2026 exchange holidays (local election, Constitution Day).
- Third-party model was stale for these ad-hoc closures; observed data includes neither date.
- Source reporting KRX statement: https://www.yna.co.kr/amp/view/AKR20260520064200008
- Remaining unexplained calendar differences: **0** in this run

## Conservative review candidates — NOT confirmed events

| Check | Candidate occurrences |
|---|---:|
| Daily close-price discontinuity over 35% | 773 |
| Outstanding-share count discontinuity over 25% | 1,677 |
| Security name change | 1,014 |
| Market transfer | 14 |
| Missing sessions between ticker observations | 4,358 |
| **Unique quarantined ticker-day rows** | **3,354** |
| Ticker codes unseen in last 20 source sessions | 617 |

These categories overlap. The 617 potentially inactive codes are **not confirmed delisted stocks**.

## Yearly quarantined ticker-days

| 2017 | 2018 | 2019 | 2020 | 2021 | 2022 | 2023 | 2024 | 2025 | 2026 |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 353 | 309 | 249 | 318 | 461 | 365 | 320 | 303 | 339 | 337 |

## Research safeguards already integrated

- If a screened CSV includes unsafe_session, a candidate event removes factors whose past 26 trading sessions overlap it.
- Five- and ten-day forward-return labels are invalid if the signal day or a future holding session is flagged.
- Absence of a listed ticker on a trading date never becomes a synthetic forward-filled price.
- Historical tickers disappearing in previous years are preserved in review state.

## Still unverified / blockers

1. Confirm exact split/rights/merger events and adjusted prices from authoritative corporate-action records.
2. Independently confirm historical ordinary-share universes (including delisted and reused identifiers); a name/market change is only a heuristic flag.
3. Confirm KRX official session rules rather than assuming a third-party calendar always reflects ad-hoc holidays.
4. Add liquidity/price-limit execution checks and realistic fee/tax modelling before treating factor forward returns as actual investment profits.
5. Audit and resolve nonfatal CI warnings.

**No claim of predictive factor performance or profitable strategy has been made.**

Only derived aggregate QA and code are committed. Raw OHLCV and event-level records were kept on the ephemeral runner and removed before artifacts were published.
