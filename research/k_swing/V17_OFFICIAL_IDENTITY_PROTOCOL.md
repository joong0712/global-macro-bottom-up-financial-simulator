# K-SWING v1.7 — official historical ISIN contract and as-of join

## Official sources identified
- Financial Services Commission / Public Data Portal, **KRX Listed Stock Information V2**: https://www.data.go.kr/en/data/15094775/openapi.do — documented `basDt`, `srtnCd`, `isinCd`, `mrktCtg`; API requires a service key. A key is **not** available in this study. The API's published metadata and field semantics must be checked against a real response before using live records.
- KRX Open API service list: https://openapi.krx.co.kr/contents/OPP/INFO/service/OPPINFO004.cmd — official KOSPI/KOSDAQ daily securities information and stock base information from 2010 onward; separate authentication may be necessary.
- KIND issuer events and DART disclosure: https://kind.krx.co.kr and https://opendart.fss.or.kr — a disclosure or exchange listing alone is not a complete point-in-time corporate-action ledger.

## Implemented
`official_identity_v17.py` accepts **offline, user-provided** official response JSON and same-day observed security list. It rejects missing/ambiguous ticker–ISIN mapping, stale or future daily snapshot, incomplete pagination, duplicate observations, unsupported market, invalid identifiers, missing official success status, and any 2023+ request. It never extrapolates a current listing backwards.

Four parallel CI contract-test jobs use **synthetic records only**. The output is a summary of documentary identity matches and blocked records; it cannot certify ordinary equity share class, inactive/delisted coverage, issuer actions, historical transaction taxes, execution fills or portfolio PnL.

## Remaining BLOCKERS
1. Authorized complete 2017–22 official daily identity snapshots and KRX market/ISIN reference tables, including delisted issuers, **not obtained**.
2. Historical common-equity vs preferred/SPAC/ETF/security-type classifications and symbol reuse are not independently verified.
3. Official effective-dated issuer actions and final cash/positions on delisting are missing.
4. Historically effective-dated taxes, auction fill realism, suspensions and transaction impact still unverified.

No new backtest result or positive return is claimed. All future validation requires independent evidence and strict point-in-time joins. Existing 2023–25 project-level exposure makes those years unsuitable as pristine holdouts; 2026 remains protected for a single preregistered confirmation. No real orders or merge.
