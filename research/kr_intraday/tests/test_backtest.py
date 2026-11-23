import unittest
from datetime import datetime, timedelta
from research.kr_intraday.backtest import run


class BacktestTests(unittest.TestCase):
    def test_orb_next_bar_and_forced_flatten(self):
        start = datetime(2026, 11, 20, 9)
        bars = []
        for i in range(380):
            price = 100.0 if i < 6 else 102.0
            bars.append({"dt": start + timedelta(minutes=i), "symbol": "TEST", "open": price, "high": price+0.1, "low": price-0.1, "close": price, "volume": 1000.0})
        bars[6]["close"] = 101.0
        bars[6]["high"] = 101.1
        bars[7]["open"] = 101.0
        bars[7]["low"] = 100.95
        bars[7]["high"] = 101.1
        trades = run({("TEST", start.date()): bars})
        orb = [x for x in trades if x["strategy"] == "orb"]
        self.assertEqual(len(orb), 1)
        self.assertEqual(orb[0]["entry_time"], bars[7]["dt"].isoformat())
        self.assertEqual(orb[0]["reason"], "time")
        self.assertAlmostEqual(orb[0]["net_return"], orb[0]["gross_return"]-0.002)


if __name__ == "__main__":
    unittest.main()
