"""v1.9 break-even cost frontier from frozen v1.5 published aggregates.

No new data download, parameter fitting, 2026 unlock, or claim of alpha.
A mean 50bps net return + 50bps assumed roundtrip cost estimates the
zero-cost *arithmetic* trade return, if cost is an additive percentage-point
deduction. This is an approximation, NOT an executable trading PnL.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path

# Frozen aggregate baseline figures from V15_PAIRED_RESULTS_AUDIT.md.
# n is repeated for 5- and 10-day horizons: do NOT call rows independent.
ROWS = (
    ("ichi_ma", "2019-20", 5, 37, -0.233),
    ("ichi_ma", "2019-20", 10, 37, -0.078),
    ("ichi_ma", "2021-22", 5, 31, -0.801),
    ("ichi_ma", "2021-22", 10, 31, -0.948),
    ("vcr_trend", "2019-20", 5, 32, -2.116),
    ("vcr_trend", "2019-20", 10, 32, -2.116),
    ("vcr_trend", "2021-22", 5, 38, -0.107),
    ("vcr_trend", "2021-22", 10, 38, -0.292),
)
ASSUMED_COST_PERCENT = 0.50


def analyze(costs_bps=(0, 20, 50, 100, 200)):
    if not costs_bps or any(not isinstance(c, (int, float))
                            or not 0 <= c <= 1000 for c in costs_bps):
        raise ValueError("Invalid nonnegative roundtrip cost grid")
    results = []
    for entry, period, horizon, n, net in ROWS:
        gross = net + ASSUMED_COST_PERCENT
        results.append({
            "entry": entry, "period": period, "horizon_sessions": horizon,
            "repeated_matched_trades": n,
            "observed_mean_net_at_50bps_percent": net,
            "implied_mean_zero_cost_percent": round(gross, 3),
            "break_even_roundtrip_bps": round(100 * gross, 2),
            "positive_at_assumed_costs_bps": {
                str(int(c)): bool(gross > c / 100) for c in costs_bps},
            "positive_at_50bps": net > 0,
        })
    # Keep family/period/horizon separate: pooled averages of correlated
    # duplicate trade opportunities are not an independent estimate.
    by_entry = {}
    for entry in ("ichi_ma", "vcr_trend"):
        by_entry[entry] = {
            "positive_at_50bps_both_periods_for_any_fixed_horizon": any(
                all(next(r for r in results if r["entry"] == entry
                         and r["period"] == period
                         and r["horizon_sessions"] == h)["positive_at_50bps"]
                    for period in ("2019-20", "2021-22"))
                for h in (5, 10)),
        }
    return {
        "status": "DIAGNOSTIC_ONLY_NO_CONFIRMED_AFTER_COST_ALPHA",
        "source": "V15_PAIRED_RESULTS_AUDIT.md",
        "source_assumed_roundtrip_bps": 50,
        "costs_bps": list(costs_bps),
        "rows": results,
        "by_entry": by_entry,
        "data_reused_not_independent": True,
        "gross_cost_addback_is_approximation": True,
        "corporate_actions_and_fills_unverified": True,
        "2026_holdout_touched": False,
        "real_orders_allowed": False,
    }


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--output", required=True, type=Path)
    args = p.parse_args()
    report = analyze()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2))
    print(json.dumps({"status": report["status"],
                      "rows": len(report["rows"]), "2026_locked": True}))


if __name__ == "__main__":
    main()
