# K-SWING v0.5 — market/size controls and costs, before new algorithm search

## Why this experiment?

Previous 188-feature v0.4 sampled pilot showed apparent low-volatility Rank IC but inconsistent Top-10 gross excess (particularly ten-day in 2023). That could be confounded by market capitalization or market membership, and does not constitute tradeable alpha.

**Frozen primary hypothesis:** In 2019–2022 training, low values of `ta__atr_wilder_pct_7`, `ta__parkinson_vol_20`, `ta__garman_klass_vol_20`, `legacy__atr_pct_14`, `ta__realized_vol_60` ranked stronger. No new formula selected based on the 2023 data.

## V0.5 method

1. Re-acquire 2017–2023 data privately with `marcap_ingest --keep-raw`; require v0.2 `quality_audit` pass.
2. Join each eligible ticker's **signal-day** actual marcap `Market` and `Marcap` fields (same day T close) rather than proxying size from volume or guessing sector.
3. For each T, assign security into KOSPI/KOSDAQ and within-market 3 market-cap buckets; within each group compute rank-normalized price indicator and future return, then concatenate the ranks and compute IC. At least 8 names per group.
4. Report raw Rank IC and *within-market/size-controlled* Rank IC side-by-side. This is an exploratory statistical control, NOT a traded market-neutral portfolio.
5. For K=3/10/20 choose names using only T's signal; later unavailable or nontradable outcomes are reported as **unresolved**, never silently replaced with next-best hindsight candidates.
6. Gross forward return is hypothetically T+1 open → T+5/T+10 close; cost stress simply subtracts 20/50/100/200 bps. Capacity diagnostic checks whether a 5 million KRW hypothetical ticket is within 0.5% of **signal-day** turnover; not proof of fillability.
7. Train years 2019–2022, 2023 is reused exploratory. **2024–2025 already viewed; 2026 absolutely held out**.

## Running on your authorized machine

```sh
python -m pip install -r research/k_swing/requirements.txt
python -m research.k_swing.marcap_ingest --start-year 2017 --end-year 2023 --keep-raw --output research/k_swing/_local_data
python -m research.k_swing.quality_audit --start-year 2017 --end-year 2023 --data research/k_swing/_local_data
python -m research.k_swing.controls_v05 --data research/k_swing/_local_data --output research/k_swing/_local_data/v05_reports
```

## Not yet solved / gates before independent 2026 check

- Marketcap is marcap's point-in-day series, not yet independently reconciled to KRX issuer master / security identifier changes.
- Sector/industry control **not performed** until real historical time-stamped classifications are supplied.
- Corporate-action-adjusted stock returns and delisted share record continuity remain uncertified.
- Trading simulator does not model actual order book, open auction queue, slippage distribution, overnight gaps, cash usage or overlapping positions.
- Broker-specific fees, Korean securities transaction tax by tax regime, and exchange levies require grounded date-aware schedules.
- Many overlapping signals / strongly correlated factors: apply block-bootstrap, FDR, regime and size/sector stability tests BEFORE new formula search.
- No prediction-success or trading-profit claim follows from this pilot. Findings can be used as exploratory evidence only.

## Roadmap after v0.5

**v0.6** data/legal-quality and proper market/sector/size-neutral controls with point-in-time official sector mappings, verified corporate actions and historical listings.

**v0.7** realistically fillable portfolio backtest + walk-forward splits, position/cash/risk limits, cost/tax schedule and stress by changing market regime.

**v0.8** AI-generated candidate alpha expressions using symbolic regression/genetic programming, restricted to training data, syntax-preserved time-causality, deduplication and FDR correction.

**v0.9** preregistered frozen hypothesis and one untouched 2026 confirmation. Only then consider paper trading, not automatic money orders.

Existing Streamlit app and production modules are excluded from every phase. Keep this PR draft.