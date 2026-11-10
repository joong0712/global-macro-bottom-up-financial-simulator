# K-SWING v0.8 — actual implementation plan

Three workstreams run independently in GitHub Actions. **None** modifies the existing Streamlit site, merges into `main`, uses live brokerage orders, or opens 2026 final test data.

### 1. Official evidence reconciliation — blocked on actual access

`official_reconcile_v08.py` requires authenticated historical FSC as-of `basDt + srtnCd + isinCd`, joined to prices only on the exact same ticker AND date. No forward filling modern ticker mappings into earlier years. Records and ticker reuse are reported but never blindly reconstitute split-adjusted trading prices. Without licensed historical events and delisting outcomes, status is still **UNCERTIFIED/BLOCKED**. The optional `fsc_snapshot_v07.py` client requires `FSC_STOCK_API_KEY`, which has not been provided; tests use synthetic examples only.

### 2. Genuine old prices, explicitly provisional cash ledger

`real_execution_v08.py` repeats 2017–23 quality screening, computes **two preselected low-volatility scores** on 2023 bars, and runs **2 factors × 2 horizons × 2 K × 4 hypothetical roundtrip costs = 32 cash-ledger scenarios**. Entry next session after signal; no future information in ranking, maximum 10 positions, KRW 100m initial cash and KRW 5m ticket, 0.5% signal-day turnover fraction. Suspicious or missing intermediate corporate-action sessions block final PnL rather than turn a delisting into a free return. No actual price-limit order-book fills or real tax schedule are available.

### 3. First bounded new-expression research sandbox

`candidate_research_v08.py` defines **12 transparent formula candidates**, using 8 already-causal inputs (ATR, Parkinson, RSI, 20d momentum, relative turnover, Bollinger width, Ichimoku spread, MACD). This is *not* an autonomous profitable AI algorithm discovery. Candidate directions are chosen ONLY on 2019–20, with 2021–22 internal stability; 2023 and all later dates are completely excluded from this subexperiment.

Every experiment keeps source and period provenance, negative findings, absent official data, and published aggregate statistics only.

### What must happen before believing the strategy

1. Obtain permissioned KRX/KIND/FSC history and verify security identity, corporate actions, delisted stocks, actual taxes and exchange fills.
2. Recompute full historical ordinary-share universe and industry-neutral experiments with adjusted prices, exclusions and censored exits explicitly accounted.
3. Freeze ONE candidate (formula, direction, threshold, Top-K, entry, exits, cash, costs) before any untouched 2026 confirmation check.
4. After honest out-of-sample replication, paper trade. Live trading is not automatically authorized.

Documentation: https://github.com/joong0712/global-macro-bottom-up-financial-simulator/tree/research/k-swing-v08/research/k_swing
