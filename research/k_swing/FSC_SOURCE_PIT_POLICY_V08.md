# K-SWING — Official FSC/KRX historical data access and signal-time policy

**Source checked 2026-11-11**: [Financial Services Commission KRX listed securities API](https://www.data.go.kr/en/data/15094775/openapi.do) and [FSC stock issuance API](https://www.data.go.kr/data/15043423/openapi.do).

## Availability is different from historical report date

The official FSC issuance-data portal explicitly states that FSC data is not real-time. A data set with business as-of date T is updated **after 13:00 KST on the next business day**. Therefore, for a T-day market-close decision at 15:30 KST, even a date-labelled T official snapshot must be treated as *not yet available*. Use earliest T+1 post-13:00 public availability (or actual source-published timestamp if later), and independently resolve KRX half-days and closures. This does not mean earlier KIND corporate-action disclosures are necessarily unavailable; they need their own true disclosure timestamps.

## Operational and licensing constraints

- FSC historical listed security snapshot endpoint: `https://apis.data.go.kr/1160100/GetKrxListedInfoService_V2/getItemInfo_V2`; serviceKey required. Historic snapshots return `basDt`, `srtnCd`, `isinCd`, but one date is not full delisting, split, or rights history.
- FSC stock issuance API (V3) base path: `https://apis.data.go.kr/1160100/GetStocIssuInfoService_V3`. Issuance/equity share changes and listing/delisting dates can complement, but never substitute, official corporate-action payouts and exchange suspension/outcome history.
- The issuance API is classified **Korea Open Government License Type 2: Attribution + NONCOMMERCIAL**. For commercial exploitation the portal directs users to seek a data license from **Korea Securities Depository**. Data redistribution and user-specific credentials also need review.
- The standard portal's development request may be automatically approved but an actual service key and entitlement are still needed. Never commit keys to git; keep them in a secrets manager and never print a URL containing the key.
- Preserve source identifiers, checksums, retrieval timestamps, as-of dates, last updates and all corrections/vintages. An as-of query made today can reflect revisions not present historically.

## Research signoff gate

No strategy may be represented as survivorship-free, corporate-action-adjusted, tax-audited or executable until stock universe (including vanished securities), split/dividend/delist outcomes, broker taxes, and fills have been separately verified with official licensed records.

2026 final market confirmation remains locked; source documentation inspection does not open the holdout.
