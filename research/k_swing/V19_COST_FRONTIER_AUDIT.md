# K-SWING v1.9 — fixed-aggregate cost frontier (NO-GO)

The user asked to seek positive **after-cost** profitability. Before adding another indicator to repeatedly inspected 2019–22 data, this preregistered diagnostic asks whether the existing negative v1.5 baseline might become profitable under different assumed **roundtrip** transaction costs. This uses **only frozen published v1.5 aggregate mean trade returns**, not new market data.

## Formula
Under the *additive percentage-point cost approximation*, `gross_mean_pct ≈ observed_mean_net_at_50bps_pct + 0.50`. Break-even roundtrip cost in bps is `100 × gross_mean_pct`. Negative thresholds mean **no nonnegative cost** is profitable. Exact proportional fee/tax and variable slippage accounting may differ; this is **not** execution-quality evidence.

| Entry | Period | H | Trades (repeated across H) | 50bps net mean | Implied zero-cost mean | Break-even roundtrip bps |
|---|---|---:|---:|---:|---:|---:|
| Ichimoku+SMA | 2019–20 | 5 | 37 | -0.233% | +0.267% | 26.7 |
| Ichimoku+SMA | 2019–20 | 10 | 37 | -0.078% | +0.422% | 42.2 |
| Ichimoku+SMA | 2021–22 | 5 | 31 | -0.801% | -0.301% | -30.1 |
| Ichimoku+SMA | 2021–22 | 10 | 31 | -0.948% | -0.448% | -44.8 |
| VCR+trend | 2019–20 | 5 | 32 | -2.116% | -1.616% | -161.6 |
| VCR+trend | 2019–20 | 10 | 32 | -2.116% | -1.616% | -161.6 |
| VCR+trend | 2021–22 | 5 | 38 | -0.107% | +0.393% | 39.3 |
| VCR+trend | 2021–22 | 10 | 38 | -0.292% | +0.208% | 20.8 |

**Key result:** Even with hypothetical **zero** roundtrip trading costs, neither fixed entry/horizon baseline shows positive mean in both periods. A lower-cost broker alone cannot rescue the existing two-period strategy. Positive zero-cost estimates in one period must not be marketed as reliable alpha.

**Research boundaries:** All rows reuse matched historical trades across horizons; do not pool as independent observations or compute a fabricated confidence interval. No official corporate-action, tax schedule or fill proof; 2023–25 previously inspected elsewhere, 2026 independent confirmation remains locked. No real orders or main merge.

**Next viable research gate:** First obtain authorized complete official historical security identity/event data and independently verify cost/auction execution. Then preregister a new *low-complexity* economic hypothesis and a frozen benchmark before any evaluation. If this evidence is not obtained, status stays NO-GO.
