import unittest
from research.kr_intraday.report import summarize


class ReportTests(unittest.TestCase):
    def test_net_returns_and_profit_factor(self):
        rows = [
            {"strategy": "orb", "net_return": "0.02"},
            {"strategy": "orb", "net_return": "-0.01"},
        ]
        r = summarize(rows)["orb"]
        self.assertEqual(r["trades"], 2)
        self.assertAlmostEqual(r["win_rate"], 0.5)
        self.assertAlmostEqual(r["mean_net_return"], 0.005)
        self.assertAlmostEqual(r["profit_factor"], 2)

    def test_empty_trades(self):
        self.assertEqual(summarize([]), {})


if __name__ == "__main__":
    unittest.main()
