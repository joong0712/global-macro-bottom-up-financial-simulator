"""Sensitivity analysis on recorded gross trade returns.

This is NOT a substitute for re-running the fill engine with each slippage model.
"""
import argparse
import csv
import json
from collections import defaultdict


def cost_sensitivity(trades, costs=(0.001, 0.002, 0.004)):
    if any(c < 0 for c in costs):
        raise ValueError("costs must be nonnegative")
    grouped = defaultdict(list)
    for trade in trades:
        grouped[trade["strategy"]].append(float(trade["gross_return"]))
    output = {}
    for strategy, values in sorted(grouped.items()):
        output[strategy] = []
        for cost in costs:
            net = [v-cost for v in values]
            gains = sum(x for x in net if x > 0)
            losses = -sum(x for x in net if x < 0)
            output[strategy].append({
                "round_trip_cost_pct": cost,
                "trades": len(net),
                "mean_net_return": sum(net)/len(net) if net else None,
                "win_rate": sum(x > 0 for x in net)/len(net) if net else None,
                "profit_factor": gains/losses if losses else None,
            })
    return output


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--trades", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    with open(args.trades, newline="", encoding="utf-8") as f:
        trades = list(csv.DictReader(f))
    result = cost_sensitivity(trades)
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
