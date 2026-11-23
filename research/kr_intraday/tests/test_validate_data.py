import unittest
from research.kr_intraday.validate_data import audit


class DataAuditTests(unittest.TestCase):
    def test_gap_detected(self):
        rows = [
            {"symbol": "A", "timestamp": "2026-11-20T09:00:00"},
            {"symbol": "A", "timestamp": "2026-11-20T09:02:00"},
            {"symbol": "A", "timestamp": "2026-11-20T15:29:00"},
        ]
        issues = [x["issue"] for x in audit(rows)["issues"]]
        self.assertIn("gap", issues)

    def test_empty(self):
        self.assertEqual(audit([])["issue_count"], 0)


if __name__ == "__main__":
    unittest.main()
