import csv
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from research.kr_intraday.pipeline import run_pipeline


class PipelineTests(unittest.TestCase):
    def test_selected_symbol_only_and_future_snapshot_ignored(self):
        with tempfile.TemporaryDirectory() as folder:
            minute_path = Path(folder) / "minutes.csv"
            snapshot_path = Path(folder) / "snapshots.csv"
            start = datetime(2026, 11, 20, 9, 0)
            with minute_path.open("w", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=["timestamp","symbol","open","high","low","close","volume"])
                writer.writeheader()
                for symbol in ("A", "B"):
                    for i in range(20):
                        price = 100 if i < 6 else 102
                        writer.writerow(dict(timestamp=(start+timedelta(minutes=i)).isoformat(),
                                             symbol=symbol,open=price,high=price+0.1,
                                             low=price-0.1,close=price,volume=1000))
            with snapshot_path.open("w", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=["timestamp","symbol","sector","close","volume","baseline_turnover","prev_close","spread_bps"])
                writer.writeheader()
                writer.writerow(dict(timestamp="2026-11-20T09:09:00",symbol="A",sector="chips",close=102,volume=100,baseline_turnover=1000,prev_close=100,spread_bps=10))
                writer.writerow(dict(timestamp="2026-11-20T09:11:00",symbol="B",sector="bio",close=102,volume=100000,baseline_turnover=1,prev_close=100,spread_bps=10))
            trades, selections = run_pipeline(minute_path, snapshot_path)
            self.assertEqual(selections[start.date()], {"A"})
            self.assertTrue(all(t["symbol"] == "A" for t in trades))


if __name__ == "__main__":
    unittest.main()
