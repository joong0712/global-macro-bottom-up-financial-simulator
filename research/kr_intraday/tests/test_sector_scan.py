import unittest
from research.kr_intraday.sector_scan import scan


class SectorScanTests(unittest.TestCase):
    def test_no_future_rows(self):
        rows = [
            dict(timestamp="2026-11-20T09:01:00", symbol="A", sector="chips", close=100, volume=100, baseline_turnover=10000, prev_close=99, spread_bps=10),
            dict(timestamp="2026-11-20T09:02:00", symbol="A", sector="chips", close=100, volume=100, baseline_turnover=20000, prev_close=99, spread_bps=10),
            dict(timestamp="2026-11-20T09:03:00", symbol="B", sector="bio", close=200, volume=100000, baseline_turnover=100, prev_close=100, spread_bps=10),
        ]
        sectors, leaders = scan(rows, "2026-11-20T09:02:00")
        self.assertEqual([s["sector"] for s in sectors], ["chips"])
        self.assertEqual(leaders[0]["symbol"], "A")
        self.assertEqual(leaders[0]["relative_turnover"], 1)

    def test_spread_exclusion(self):
        rows = [dict(timestamp="2026-11-20T09:01:00", symbol="A", sector="chips", close=100, volume=100, baseline_turnover=100, prev_close=99, spread_bps=50)]
        sectors, leaders = scan(rows, "2026-11-20T09:01:00")
        self.assertEqual(len(sectors), 1)
        self.assertFalse(leaders)
