"""Research-only minute-bar signal and conservative execution prototype."""
import argparse
import csv
from collections import defaultdict
from datetime import datetime, time
from pathlib import Path

REQUIRED = ("timestamp", "symbol", "open", "high", "low", "close", "volume")
STRATEGIES = ("orb", "vwap", "momentum")


def read_bars(path):
    groups = defaultdict(list)
    seen = set()
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        if not set(REQUIRED).issubset(reader.fieldnames or []):
            raise ValueError("missing required CSV columns")
        for row in reader:
            dt = datetime.fromisoformat(row["timestamp"])
            if dt.tzinfo is not None:
                raise ValueError("timestamps must be Asia/Seoul local without offset")
            key = (dt, row["symbol"])
            if key in seen:
                raise ValueError("duplicate minute/symbol")
            seen.add(key)
            bar = {"dt": dt, "symbol": row["symbol"]}
            for col in ("open", "high", "low", "close", "volume"):
                bar[col] = float(row[col])
            if min(bar[x] for x in ("open", "high", "low", "close")) <= 0 or bar["volume"] < 0:
                raise ValueError("invalid OHLCV")
            if not (bar["low"] <= min(bar["open"], bar["close"]) <= max(bar["open"], bar["close"]) <= bar["high"]):
                raise ValueError("inconsistent OHLC")
            if not time(9, 0) <= dt.time() <= time(15, 29):
                raise ValueError("outside regular session")
            groups[(row["symbol"], dt.date())].append(bar)
    for bars in groups.values():
        bars.sort(key=lambda b: b["dt"])
    return groups


def signal(strategy, bars, i, cum_pv, cum_vol):
    b = bars[i]
    t = b["dt"].time()
    if not time(9, 5) <= t < time(14, 30):
        return False
    if strategy == "orb":
        opening = [x for x in bars[:i] if time(9, 0) <= x["dt"].time() < time(9, 5)]
        return len(opening) == 5 and b["close"] > max(x["high"] for x in opening) and bars[i-1]["close"] <= max(x["high"] for x in opening)
    if strategy == "vwap":
        if i < 1 or cum_vol[i] <= 0 or cum_vol[i-1] <= 0:
            return False
        return bars[i-1]["close"] <= cum_pv[i-1]/cum_vol[i-1] and b["close"] > cum_pv[i]/cum_vol[i]
    if strategy == "momentum":
        if i < 15:
            return False
        recent = bars[i-5:i]
        prior = bars[i-15:i-5]
        return prior[-1]["close"] > prior[0]["open"] * 1.03 and b["close"] > max(x["high"] for x in recent) and (max(x["high"] for x in recent) - min(x["low"] for x in recent))/b["close"] <= 0.02
    raise ValueError(strategy)


def run(groups, risk_pct=0.01, target_r=2.0, round_trip_cost_pct=0.002, min_signal_time=None):
    if not 0 < risk_pct < 1 or target_r <= 0 or round_trip_cost_pct < 0:
        raise ValueError("invalid parameters")
    trades = []
    for (symbol, day), bars in sorted(groups.items()):
        if len(bars) < 8:
            continue
        pv, vol = [], []
        for b in bars:
            pv.append((pv[-1] if pv else 0) + (b["high"]+b["low"]+b["close"])/3*b["volume"])
            vol.append((vol[-1] if vol else 0) + b["volume"])
        for strategy in STRATEGIES:
            position = None
            pending = False
            for i, b in enumerate(bars):
                if position is None and pending:
                    pending = False
                    if b["dt"].time() < time(15, 10):
                        entry = b["open"]
                        position = {"entry": entry, "stop": entry*(1-risk_pct), "target": entry*(1+risk_pct*target_r), "entry_time": b["dt"].isoformat()}
                if position is not None:
                    exit_price = None
                    reason = None
                    if b["dt"].time() >= time(15, 10):
                        exit_price, reason = b["open"], "time"
                    elif b["low"] <= position["stop"]:
                        exit_price, reason = min(b["open"], position["stop"]), "stop"
                    elif b["high"] >= position["target"]:
                        exit_price, reason = position["target"], "target"
                    if exit_price is not None:
                        gross = exit_price/position["entry"] - 1
                        trades.append({"date": str(day), "symbol": symbol, "strategy": strategy, "entry_time": position["entry_time"], "exit_time": b["dt"].isoformat(), "entry": round(position["entry"], 5), "exit": round(exit_price, 5), "reason": reason, "gross_return": round(gross, 8), "net_return": round(gross-round_trip_cost_pct, 8)})
                        position = None
                        # At most one trade per symbol per strategy per day in v1.
                        break
                if position is None and i+1 < len(bars) and (min_signal_time is None or b["dt"].time() >= min_signal_time) and signal(strategy, bars, i, pv, vol):
                    pending = True
            # Missing end-of-day bars must not silently turn into overnight positions.
            if position is not None:
                b = bars[-1]
                gross = b["close"]/position["entry"] - 1
                trades.append({"date": str(day), "symbol": symbol, "strategy": strategy, "entry_time": position["entry_time"], "exit_time": b["dt"].isoformat(), "entry": round(position["entry"], 5), "exit": round(b["close"], 5), "reason": "data_end", "gross_return": round(gross, 8), "net_return": round(gross-round_trip_cost_pct, 8)})
    return trades


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--input", required=True)
    p.add_argument("--output", required=True)
    p.add_argument("--risk-pct", type=float, default=0.01)
    p.add_argument("--target-r", type=float, default=2.0)
    p.add_argument("--round-trip-cost-pct", type=float, default=0.002)
    args = p.parse_args()
    trades = run(read_bars(args.input), args.risk_pct, args.target_r, args.round_trip_cost_pct)
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["date", "symbol", "strategy", "entry_time", "exit_time", "entry", "exit", "reason", "gross_return", "net_return"])
        writer.writeheader()
        writer.writerows(trades)
    print(f"wrote {len(trades)} research trades to {out}")


if __name__ == "__main__":
    main()
