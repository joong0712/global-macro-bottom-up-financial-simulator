"""Point-in-time sector and stock ranking from completed minute bars."""
from collections import defaultdict
from datetime import datetime


def scan(rows, asof, top_sectors=3, leaders_per_sector=2):
    """Rank sectors and leaders using only rows available at asof.

    Each row: timestamp, symbol, sector, close, volume, baseline_turnover,
    prev_close, spread_bps. Baseline is cumulative same-time historical
    average calculated exclusively from PRIOR sessions.
    """
    if isinstance(asof, str):
        asof = datetime.fromisoformat(asof)
    by_symbol = defaultdict(list)
    for row in rows:
        dt = datetime.fromisoformat(row["timestamp"])
        if dt.date() != asof.date() or dt > asof:
            continue
        if row.get("sector") and row.get("symbol"):
            by_symbol[row["symbol"]].append((dt, row))
    stocks = []
    for symbol, history in by_symbol.items():
        history.sort(key=lambda x: x[0])
        latest = history[-1][1]
        close = float(latest["close"])
        prev_close = float(latest["prev_close"])
        baseline = float(latest["baseline_turnover"])
        spread = float(latest.get("spread_bps", 0))
        if close <= 0 or prev_close <= 0 or baseline <= 0 or spread < 0:
            continue
        if any(float(r["volume"]) < 0 for _, r in history):
            continue
        turnover = sum(float(r["close"]) * float(r["volume"]) for _, r in history)
        stocks.append(dict(symbol=symbol, sector=latest["sector"], turnover=turnover,
                           relative_turnover=turnover/baseline,
                           return_pct=(close/prev_close-1)*100,
                           spread_bps=spread))
    sectors = defaultdict(list)
    for stock in stocks:
        sectors[stock["sector"]].append(stock)
    ranked = []
    for name, members in sectors.items():
        total = sum(x["turnover"] for x in members)
        base = sum(x["turnover"]/x["relative_turnover"] for x in members)
        ranked.append(dict(sector=name, turnover=total,
                           relative_turnover=total/base if base else 0,
                           breadth=sum(x["return_pct"] > 0 for x in members)/len(members),
                           mean_return_pct=sum(x["return_pct"] for x in members)/len(members),
                           members=len(members)))
    ranked.sort(key=lambda x: (x["relative_turnover"], x["breadth"], x["mean_return_pct"]), reverse=True)
    selected = {x["sector"] for x in ranked[:top_sectors]}
    leaders = []
    for sector in selected:
        candidates = [x for x in stocks if x["sector"] == sector and x["spread_bps"] <= 30]
        candidates.sort(key=lambda x: (x["relative_turnover"], x["return_pct"]), reverse=True)
        leaders.extend(candidates[:leaders_per_sector])
    return ranked, sorted(leaders, key=lambda x: (x["relative_turnover"], x["return_pct"]), reverse=True)
