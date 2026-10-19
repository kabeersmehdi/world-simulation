import json
import unittest

from worldsim import markets

from .helpers import NOW, NOW_ISO, isolated_root


def fake_fetch(url):
    if "missing" in url:
        return "[]"
    return json.dumps([{"question": "Will it happen?", "outcomePrices": "[\"0.295\", \"0.705\"]", "endDate": "2026-10-28T00:00:00Z", "volumeNum": 1000, "closed": False}])


class MarketTests(unittest.TestCase):
    def test_snapshot_reads_outcome_price(self):
        row = markets.snapshot({"slug": "x-market", "label": "X", "outcome_index": 1}, NOW_ISO, fake_fetch, isolated_root())
        self.assertAlmostEqual(row["probability"], 0.705)
        self.assertEqual(row["end_date"], "2026-10-28")

    def test_missing_market_is_reported_not_crashed(self):
        root = isolated_root()
        (root / "config" / "markets.json").write_text(json.dumps({"markets": [
            {"slug": "good-one", "label": "Good", "countries": ["israel"], "topic": "election", "outcome_index": 0},
            {"slug": "missing-one", "label": "Gone", "countries": ["israel"], "topic": "election", "outcome_index": 0}]}))
        rows, report = markets.collect(root, fake_fetch, NOW)
        self.assertEqual(len(rows), 1)
        self.assertFalse(report[1]["ok"])

    def test_board_change_over_time(self):
        root = isolated_root()
        markets.save([{"slug": "good-one", "source": "polymarket", "at": "2026-10-10T00:00:00+00:00", "probability": 0.2, "question": "Q?", "end_date": None, "volume": None, "closed": False},
                      {"slug": "good-one", "source": "polymarket", "at": "2026-10-18T00:00:00+00:00", "probability": 0.35, "question": "Q?", "end_date": None, "volume": None, "closed": False}], root)
        (root / "config" / "markets.json").write_text(json.dumps({"markets": [{"slug": "good-one", "label": "Good", "countries": ["israel"], "topic": "election", "outcome_index": 0}]}))
        b = markets.board(root, NOW)[0]
        self.assertAlmostEqual(b["probability"], 0.35)
        self.assertAlmostEqual(b["change"], 0.15)


if __name__ == "__main__":
    unittest.main()
