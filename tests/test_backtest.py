import json
import unittest
from datetime import datetime, timezone

from worldsim import backtest

from .helpers import isolated_root

CLOSE = datetime(2026, 9, 30, tzinfo=timezone.utc).timestamp()
DAY = 86400


def market(slug, yes, volume=50000, event="E"):
    return {"slug": slug, "question": f"Ceasefire question {slug}?", "closed": True, "outcomePrices": json.dumps([str(yes), str(1 - yes)]),
            "closedTime": "2026-09-30 00:00:00+00", "endDate": "2026-10-01T00:00:00Z", "volumeNum": volume,
            "clobTokenIds": json.dumps([f"tok-{slug}", "x"])}


def fake_fetch(url):
    if "public-search" in url:
        return json.dumps({"events": [{"title": "E", "markets": [market("a", 1), market("b", 0), market("c", 0.5), market("thin", 1, volume=5)]}]})
    tok = url.split("market=")[1].split("&")[0]
    p = {"tok-a": 0.8, "tok-b": 0.3}[tok]
    return json.dumps({"history": [{"t": CLOSE - 40 * DAY, "p": p}, {"t": CLOSE - 2 * DAY, "p": p}]})


class BacktestTests(unittest.TestCase):
    def test_outcome_needs_settled_price(self):
        self.assertTrue(backtest.outcome_of({"outcomePrices": '["0.995", "0.005"]'}))
        self.assertFalse(backtest.outcome_of({"outcomePrices": '["0", "1"]'}))
        self.assertIsNone(backtest.outcome_of({"outcomePrices": '["0.5", "0.5"]'}))

    def test_close_time_takes_the_earlier(self):
        self.assertEqual(backtest.close_time({"closedTime": "2026-09-30 00:00:00+00", "endDate": "2026-10-01T00:00:00Z"}).day, 30)

    def test_price_before(self):
        h = [{"t": 10, "p": 0.1}, {"t": 20, "p": 0.2}]
        self.assertIsNone(backtest.price_before(h, 5))
        self.assertEqual(backtest.price_before(h, 15), 0.1)

    def test_run_offline_scores_and_skips(self):
        root = isolated_root()
        (root / "config" / "backtest.json").write_text(json.dumps({"queries": ["x"], "min_volume": 1000, "ceasefire_words": ["ceasefire"]}))
        r = backtest.run(root, fetch=fake_fetch, pause=0)
        self.assertEqual(sorted(row["slug"] for row in r["rows"]), ["a", "b"])
        h7 = r["summary"][0]["horizons"]["7"]
        self.assertEqual(h7["n"], 2)
        self.assertAlmostEqual(h7["market_brier"], ((0.8 - 1) ** 2 + 0.3 ** 2) / 2)
        self.assertEqual(h7["hit_rate"], 1.0)
        self.assertTrue((root / "data" / "backtests" / "polymarket-geopolitics.json").exists())
        self.assertIn("recent", backtest.load(root))


if __name__ == "__main__":
    unittest.main()
