"""Produce SYNTHETIC ONLY market-like data (not actual historical quotations)."""
import argparse
from pathlib import Path
import numpy as np
import pandas as pd


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    parser.add_argument("--tickers", type=int, default=30)
    parser.add_argument("--sessions", type=int, default=220)
    args = parser.parse_args()
    if args.tickers < 1 or args.sessions < 30:
        parser.error("tickers>=1 and sessions>=30 required")
    rng = np.random.default_rng(42)
    dates = pd.bdate_range("2023-01-02", periods=args.sessions)
    rows = []
    for code in range(args.tickers):
        price = 1000 + 20 * code
        for date in dates:
            open_ = price * np.exp(rng.normal(0, .007))
            close = open_ * np.exp(rng.normal(.0002, .017))
            high = max(open_, close) * (1 + rng.uniform(0, .014))
            low = min(open_, close) * (1 - rng.uniform(0, .014))
            volume = int(rng.integers(150_000, 2_000_000))
            rows.append((date.strftime("%Y-%m-%d"), f"{code + 1:06d}",
                         open_, high, low, close, volume, volume * (open_ + close) / 2))
            price = close
    data = pd.DataFrame(rows, columns=[
        "date", "ticker", "open", "high", "low", "close", "volume", "turnover"
    ])
    destination = Path(args.output)
    destination.parent.mkdir(parents=True, exist_ok=True)
    data.to_csv(destination, index=False)
    print(f"SYNTHETIC ONLY: {len(data)} rows -> {destination}")


if __name__ == "__main__":
    main()
