"""Audit minute data completeness and suspicious gaps before backtesting."""
import argparse
import csv
import json
from collections import defaultdict
from datetime import datetime, timedelta, time


def audit(rows):
    by_key = defaultdict(list)
    seen = set()
    problems = []
    for row in rows:
        dt = datetime.fromisoformat(row["timestamp"])
        key = (row["symbol"], dt.date())
        if (row["symbol"], dt) in seen:
            problems.append({"symbol": row["symbol"], "date": str(dt.date()), "issue": "duplicate", "timestamp": dt.isoformat()})
        seen.add((row["symbol"], dt))
        by_key[key].append(dt)
    for (symbol, day), timestamps in sorted(by_key.items()):
        timestamps.sort()
        if timestamps[0].time() != time(9):
            problems.append({"symbol": symbol, "date": str(day), "issue": "missing_open", "timestamp": timestamps[0].isoformat()})
        if timestamps[-1].time() != time(15, 29):
            problems.append({"symbol": symbol, "date": str(day), "issue": "missing_close", "timestamp": timestamps[-1].isoformat()})
        for previous, current in zip(timestamps, timestamps[1:]):
            if current-previous > timedelta(minutes=1):
                problems.append({"symbol": symbol, "date": str(day), "issue": "gap", "from": previous.isoformat(), "to": current.isoformat()})
    return {"symbol_days": len(by_key), "issues": problems, "issue_count": len(problems)}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--minutes", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    with open(args.minutes, newline="", encoding="utf-8") as f:
        report = audit(list(csv.DictReader(f)))
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    print(json.dumps({"symbol_days": report["symbol_days"], "issue_count": report["issue_count"]}))


if __name__ == "__main__":
    main()
