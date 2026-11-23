"""Descriptive trade-level metrics; not portfolio equity or risk-adjusted returns."""
import argparse
import csv
import json
from collections import defaultdict
from math import sqrt


def summarize(trades):
    by_strategy = defaultdict(list)
    for row in trades:
        by_strategy[row["strategy"]].append(float(row["net_return"]))
    result = {}
    for strategy, values in sorted(by_strategy.items()):
        n = len(values)
        wins = [v for v in values if v > 0]
        losses = [v for v in values if v < 0]
        gross_profit = sum(wins)
        gross_loss = -sum(losses)
        mean = sum(values)/n
        variance = sum((v-mean)**2 for v in values)/(n-1) if n > 1 else None
        result[strategy] = {
            "trades": n,
            "win_rate": len(wins)/n,
            "mean_net_return": mean,
            "median_net_return": sorted(values)[n//2] if n % 2 else (sorted(values)[n//2-1]+sorted(values)[n//2])/2,
            "profit_factor": gross_profit/gross_loss if gross_loss else None,
            "sample_std": sqrt(variance) if variance is not None else None,
            "note": "Per-trade descriptive metrics; overlapping trades, position sizing, portfolio MDD and capital constraints not modeled."
        }
    return result


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--trades", required=True)
    p.add_argument("--output", required=True)
    args = p.parse_args()
    with open(args.trades, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    report = summarize(rows)
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
