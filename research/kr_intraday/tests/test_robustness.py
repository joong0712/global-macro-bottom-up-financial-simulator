import unittest
from research.kr_intraday.robustness import cost_sensitivity


class RobustnessTests(unittest.TestCase):
    def test_higher_cost_lowers_mean(self):
        trades = [{"strategy": "orb", "gross_return": "0.01"},
                  {"strategy": "orb", "gross_return": "-0.005"}]
        rows = cost_sensitivity(trades)["orb"]
        self.assertEqual([r["trades"] for r in rows], [2, 2, 2])
        self.assertGreater(rows[0]["mean_net_return"], rows[1]["mean_net_return"])
        self.assertGreater(rows[1]["mean_net_return"], rows[2]["mean_net_return"])

    def test_reject_negative_cost(self):
        with self.assertRaises(ValueError):
            cost_sensitivity([], costs=(-0.01,))


if __name__ == "__main__":
    unittest.main()
