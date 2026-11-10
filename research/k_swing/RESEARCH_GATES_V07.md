# K-SWING v0.7 — prerequisites before inventing or trading a new alpha algorithm

## Three parallel independent workflows

**A. KRX/KIND/FSC official data gate**: `official_events_v07.py` validates historical ISIN, event, source record ID, true release time, event effective date and authoritative provenance. **This does not currently download or certify historical events.** The CI deliberately emits BLOCKED until permissioned official history and completeness verification are supplied. A marcap 35% close jump or a missing ticker is not an independently verified split or delisting.

**B. Statistical skepticism**: `statistical_stress_v07.py` reconstructs 2023 daily cross-sectional Rank IC for *30 factor/horizon combinations selected on 2019–22 training only*, uses 20-session moving block bootstrap and shared time-block sign flips; reports descriptive confidence intervals and 30-way BH q-values/max-statistic checks. Null symmetry and reuse of 2023 data mean these cannot establish independent significance. Overlap means naive p-values are invalid.

**C. Trade cash and execution prototype**: `execution_prototype_v07.py` explicitly models candidate selection at T close (not based on future availability), entry at T+1 open, exit at T+H close, ticket/position/cash limits, T turnover capacity checks, assumed 20/50/100/200 bps and no hindsight replacement. An unresolved exit blocks final profit reporting. Tests are synthetic only; actual auction fills and date-specific fees/taxes still unverified.

## Official source availability and gates

- KRX OPEN API listed services: https://openapi.krx.co.kr/contents/OPP/INFO/service/OPPINFO004.cmd — daily trading and listed security basic data back to 2010, requires approved authenticated service access; an API catalog is not a downloaded verified history.
- KIND disclosure categories: https://kind.krx.co.kr/disclosure/details.do?method=searchDetailsMain — split/merger, trading halt/resume, delisting announcements, source disclosure timestamps must be tied to exact ISIN identities.
- Financial Services Commission stock issuance history: https://www.data.go.kr/data/15043423/openapi.do — ISIN/issuance, share count, listing and delisting dates; government page flags **attribution/noncommercial reuse (공공누리 제2유형)**, and commercial use may require agreement with KSD. A service API key/use approval is required; never store credentials in GitHub code or logs.
- FSC listed-securities catalog/API: https://www.data.go.kr/en/data/15094775/openapi.do — date and historical security reference records. Each observed date is not automatically a complete historical regular-share/sector universe.

## Status definitions — do not overstate

- OFFICIAL HISTORY: **BLOCKED** until approved key, sufficient point-in-time historical ISIN records, verified events (including delist/returns), licensing, coverage metrics.
- STATISTICS: exploratory robustness, not a pristine 2023 test. **2026 remains untouched**.
- EXECUTION: price-print/cash simulation with hypothetical costs, *not* official venue fills or audited brokerage PnL. Honest status remains provisional even if synthetic unit tests pass.

## After the gates

1. Acquire permissioned official KRX/KIND/FSC histories, verify point-in-time mapping and adjust actual price/volume/returns, including ceased listings.
2. Re-evaluate fixed 188-feature baselines with **full historical ordinary-share universe**, industry/size effects and robust nonindependence/multiple testing controls.
3. Validate realistic 5–10-session cash portfolio with audited transaction tax regimes and conservative open auction limits; investigate drawdown, blocked exits and capacity.
4. Only then freeze rules and use AI to generate a bounded family of new expressions on training data, with preregistration and a one-time 2026 untouched verification.

**No production Streamlit web changes, no writes to main, no actual brokerage orders.**