"""Point-in-time sector selection -> minute-bar signal backtest.

Selection snapshots must be generated with historical data available at the
snapshot time, including baseline_turnover from strictly prior sessions.
"""
import argparse
import csv
from collections import defaultdict
from datetime import datetime, time
from pathlib import Path
from research.kr_intraday.backtest import read_bars, run
from research.kr_intraday.sector_scan import scan

COLUMNS = ("date", "symbol", "strategy", "entry_time", "exit_time", "entry",
           "exit", "reason", "gross_return", "net_return")


def selected_groups(groups, snapshots, selection_time=time(9, 10),
                    top_sectors=3, leaders_per_sector=2):
    by_day = defaultdict(list)
    for row in snapshots:
        dt = datetime.fromisoformat(row["timestamp"])
        by_day[dt.date()].append(row)
    result = {}
    selections = {}
    for (symbol, day), bars in groups.items():
        if day not in selections:
            asof = datetime.combine(day, selection_time)
            sectors, leaders = scan(by_day.get(day, []), asof,
                                    top_sectors, leaders_per_sector)
            selections[day] = {x["symbol"] for x in leaders}
        if symbol in selections[day]:
            # Strategy engine may inspect only completed minute bars at each signal.
            result[(symbol, day)] = bars
    return result, selections


def run_pipeline(minute_csv, snapshot_csv, **kwargs):
    groups = read_bars(minute_csv)
    with open(snapshot_csv, newline="", encoding="utf-8") as f:
        snapshots = list(csv.DictReader(f))
    if not set(("timestamp", "symbol", "sector", "close", "volume",
                "baseline_turnover", "prev_close")).issubset(snapshots[0].keys() if snapshots else []):
        raise ValueError("missing snapshot columns or empty snapshot file")
    selected, selections = selected_groups(groups, snapshots)
    return run(selected, **kwargs), selections


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--minutes", required=True)
    parser.add_argument("--snapshots", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--round-trip-cost-pct", type=float, default=0.002)
    args = parser.parse_args()
    trades, selections = run_pipeline(args.minutes, args.snapshots,
                                     round_trip_cost_pct=args.round_trip_cost_pct)
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=COLUMNS)
        writer.writeheader()
        writer.writerows(trades)
    print(f"selected {sum(map(len, selections.values()))} symbol-days; {len(trades)} trades")
    print("No historical performance claim until real point-in-time data and realistic fills are validated.")


if __name__ == "__main__":
    main()
