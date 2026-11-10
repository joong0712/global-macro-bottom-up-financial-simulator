# K-SWING v0.7 — hard gates, exploratory block statistics and provisional execution

## Parallel execution provenance

- Three independent jobs ALL **succeeded** in [GitHub Actions run #42883409936](https://github.com/joong0712/global-macro-bottom-up-financial-simulator/actions/runs/42883409936).
- Official verification guard unit tests: **4 passed**. Output status **BLOCKED_OFFICIAL_HISTORY_NOT_PROVIDED**; this is correct. NO historical official corporate action/delisting ledger was acquired and NO adjusted price verification happened.
- Next-open execution prototype unit tests: **5 passed** on synthetic prices. Cash, ticket, capacity, no hindsight replacement and unknown exits exercised; **NOT real order-book fills**.
- Exploratory 20-session block-bootstrap/BH FDR statistics: tests passed, then completed 2017–2023 marcap download and quarantine; 2023 stats generated. No 2024–2026 dates read.

## Official data: current boundary

KRX official service list: https://openapi.krx.co.kr/contents/OPP/INFO/service/OPPINFO004.cmd — daily stock/issuer base reference since 2010, requires service authorization.

KIND disclosures: https://kind.krx.co.kr/disclosure/details.do?method=searchDetailsMain — corporate splits/rights/mergers/delisting/suspension announcements.

FSC stock issuance history: https://www.data.go.kr/data/15043423/openapi.do — issuance, share count, listing/delisting dates; government portal advertises **attribution + noncommercial use** and directs commercial users to an agreement with Korea Securities Depository.

FSC listed-stock issuer reference: https://www.data.go.kr/en/data/15094775/openapi.do — authenticated historic date snapshots, **not a full corporate-action event list**. Optional `fsc_snapshot_v07.py` refuses to fetch without `FSC_STOCK_API_KEY`; one date's snapshot is never treated as complete history. Key must be provided through an authorized GitHub Action secret or locally, never pasted into source.

Current independent verified event records acquired: **0**. This is a blocker for any definitive delisting-adjusted and tax-adjusted trading PnL, NOT an excuse to mark missing returns as zero or ignore dead stocks.

## 2023 block-bootstrap / FDR exploratory findings

- [Artifacts](https://github.com/joong0712/global-macro-bottom-up-financial-simulator/actions/runs/42883409936/artifacts/13795635656) — aggregate only, short retention.
- SHA-256 sampled 176 ticker codes, 28,276 eligible 2023 ticker-days, 235 evaluable signal dates and 7,050 factor/horizon/day Rank IC records.
- Factor/horizon tests: 30 (15 training-selected per horizon). No new factor fitted in 2023.
- Mean daily oriented cross-sectional Rank IC for Garman–Klass 20d volatility, H=10: **+0.1133**; 95% 20-day moving-block-bootstrap interval **[+0.0658,+0.1677]**.
- Garman–Klass 20d volatility, H=5: mean IC **+0.0983**; interval **[+0.0603,+0.1403]**.
- At a nominal 0.05 cutoff, **28/30** assumptions-based BH q-values are below 0.05; **23/30** max-factor block-signflip p-values below 0.05.

**These are NOT independently verified statistical discoveries.** The 2023 period had already been inspected and the factor selection was influenced by earlier train results. Sign-flip p-values rely on 20-session joint block-sign symmetry; dates have overlapping return outcomes and indicators are strongly correlated. BH controls only under suitable dependence/null assumptions. None of these statistics establishes executable PnL or out-of-sample economic alpha.

## Trade simulator limitations

- `execution_prototype_v07.py` demonstrates signal T close, next-session T+1 open print entry, original horizon's closing print exit, position and cash constraints, no selecting an 11th stock when a selected top-10 pick fails, and missing exit triggers BLOCKED performance status.
- Fee/tax/slippage bps are **assumed sensitivity parameters**, not confirmed Korean 2019–2023 exchange tax regimes and broker fills.
- Runs thus far are synthetic only; the existing v0.5 data-based 20/50/100/200bp gross-return stress is not a capital-booked backtest.
- Real fills, matching market auctions, price limits, overnight available liquidity, corporate-action adjusted positions and delisting outcomes require further evidence.

## Required to unlock a final trading hypothesis

1. Acquire licensed/authenticated per-date KRX basic information and official KIND/FSC corporate actions, reconcile historical ISIN, security type, listing/delisting status and adjusted returns.
2. Obtain period-specific official tax/fee schedules, or keep fees as explicit pessimistic scenarios and do NOT claim actual net PnL.
3. Construct survivorship-aware complete market universe and risk-adjusted self-financing walk-forward execution test, including blocked entries/exits.
4. Only then preregister a single formula/market regime/entry/exit/cash rule and inspect 2026 holdout once, without cherry-picking its result.

**No writes to main or the original Streamlit web application. PR remains Draft.**