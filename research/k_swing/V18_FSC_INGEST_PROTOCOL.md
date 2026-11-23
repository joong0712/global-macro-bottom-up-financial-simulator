# K-SWING v1.8 — authenticated FSC ingestion ready, access still blocked

## New official-source findings
FSC KRX Listed Info V2 is documented at https://www.data.go.kr/data/15094775/openapi.do. Its catalog explicitly states **Korea Open Government License Type 4** (attribution, non-commercial, no derivatives) and restrictions on redistribution. Commercial use requires separate permission/purchase from KRX. This matters if the project becomes a paid stock-picking service. No data purchase or rights request was made.

**Important v1.7 correction:** Real FSC `srtnCd` can be prefixed `A` (for example `A900110`); foreign-listed securities may have `HK...` ISIN. The previous v1.7 parser demanded six digits and `KR...` ISIN and could wrongly reject valid rows. v1.8 supports the actual documented shapes, with explicit mapping and blocking on ambiguous identities.

## Implemented
- `fsc_ingest_v18.py`: fetch one research-era day with `FSC_SERVICE_KEY` supplied by the operator's environment, parse all official pages, reject incomplete/mismatched totals, duplicate records, invalid dates, non-success API codes and future 2023–2026 access. Private raw output chmod 0600. No API URLs or secrets printed.
- `fsc_reconcile_v18.py`: reconcile complete daily official records to observed six-digit historical market symbols; preserve foreign ISINs and A-prefixed code semantics, fail closed on ambiguous identity. Only **aggregate counts** are printed. No source rows are uploaded as CI artifacts.
- Two parallel CI jobs test synthetic pagination and identifier scenarios. **No real FSC records are fetched in CI** because no authorized key was provided.

## Operator prerequisites
1. Apply for API access at https://www.data.go.kr/data/15094775/openapi.do (development use is listed as auto-approved).
2. Set `FSC_SERVICE_KEY` in a **local environment or approved private runner**; never commit the key or paste it into a public issue/PR.
3. Run `python -m research.k_swing.fsc_ingest_v18 --day 20200102 --private-output ./private/fsc_20200102.json`.
4. Independently supply a *private* `[{"date":"20200102","ticker":"005930"}]` observed-list JSON, then run `python -m research.k_swing.fsc_reconcile_v18 --private-day-json ./private/fsc_20200102.json --private-observed-json ./private/observed_20200102.json --aggregate-output ./private/reconciliation_summary.json`.
5. Audit the historical publication vintage. FSC metadata states daily data is published after 13:00 KST on the **next business day**. A daily record with `basDt=T` is not necessarily public at the **T close**. Identity matching is **retrospective reference reconciliation only**, not a T-close signal feature.
6. Confirm official security-type, delisting coverage, effective corporate actions, tax/fees and venue fills before trusting strategy PnL.

## Research verdict
**BLOCKED — official key/data not available; no verified new alpha.** The existing v1.5 negative after-cost trade results stand. No actual orders, 2026 independent confirmation, paid purchase or main merge.
