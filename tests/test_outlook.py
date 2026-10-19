import unittest
from datetime import date

from worldsim import outlook

from .helpers import good_forecast

TODAY = date(2026, 10, 19)


def fc(fid, p, deadline, group=None, topic="election", slug=None):
    return good_forecast(id=fid, topic=topic, deadline=deadline, exclusive_group=group,
                         market={"source": "polymarket", "slug": slug} if slug else None,
                         question=f"Will {fid} be the next prime minister of Israel?",
                         history=[{"at": "2026-10-01T00:00:00+00:00", "probability": p, "rationale": "Test entry for outlook."}])


class OutlookTests(unittest.TestCase):
    def test_verdicts(self):
        self.assertEqual(outlook.verdict(0.95), "Very likely")
        self.assertEqual(outlook.verdict(0.5), "Toss-up")
        self.assertEqual(outlook.verdict(0.2), "Unlikely")
        self.assertEqual(outlook.verdict(0.01), "Very unlikely")

    def test_gap_words(self):
        self.assertEqual(outlook.gap_words(0.50, 0.48), "Same")
        self.assertEqual(outlook.gap_words(0.86, 0.73), "We're 13 pts higher")
        self.assertEqual(outlook.gap_words(0.30, 0.45), "We're 15 pts lower")
        self.assertEqual(outlook.gap_words(0.30, None), "No market")

    def test_groups_and_market_join(self):
        live = [fc("fc-a", 0.6, "2026-10-21T00:00:00+00:00", slug="a"), fc("fc-b", 0.2, "2026-11-10T00:00:00+00:00"),
                fc("fc-c", 0.4, "2027-03-01T00:00:00+00:00"), fc("fc-d", 0.4, "2026-10-10T00:00:00+00:00")]
        rows = outlook.forecast_rows(live, {"a": (0.55, "x")}, None, TODAY)
        self.assertEqual([(r["id"], r["group"]) for r in rows],
                         [("fc-d", "Past due"), ("fc-a", "This week"), ("fc-b", "This month"), ("fc-c", "Later")])
        self.assertEqual(rows[1]["market"], 0.55)
        self.assertEqual(rows[1]["gap"], "We're 5 pts higher")

    def test_headline_picks_group_favorite(self):
        live = [fc("Eisenkot", 0.47, "2027-12-31T00:00:00+00:00", "il-next-pm-2026"),
                fc("Netanyahu", 0.30, "2027-12-31T00:00:00+00:00", "il-next-pm-2026")]
        for f in live:
            f["id"] = "fc-" + f["id"].lower()
        rows = outlook.forecast_rows(live, {}, None, TODAY)
        h = outlook.headlines(live, rows, [])
        self.assertEqual(h[0]["title"], "Next Israeli prime minister")
        self.assertTrue(h[0]["answer"].startswith("Eisenkot, 47%"))

    def test_military_forecasts_get_stock_moves(self):
        reactions = {"assets": [{"ticker": "ESLT", "name": "Elbit", "summary": {
            "1": {"unusual": True, "holds_without_largest": True, "mean": 2.4, "measure": "vs SPY"},
            "5": {"unusual": False, "holds_without_largest": False, "mean": 1.0, "measure": "vs SPY"}}}]}
        rows = outlook.forecast_rows([fc("fc-m", 0.3, "2026-10-30T00:00:00+00:00", topic="military"),
                                      fc("fc-e", 0.3, "2026-10-30T00:00:00+00:00")], {}, reactions, TODAY)
        by = {r["id"]: r for r in rows}
        self.assertEqual(by["fc-m"]["stock_moves"][0]["text"], "Elbit +2.4% vs the S&P after 1 trading day")
        self.assertEqual(by["fc-e"]["stock_moves"], [])

    def test_brief_skips_long_shots_and_caps(self):
        items = [{"date": "2026-10-2%d" % i, "kind": "forecast", "title": f"Item {i}", "p": 0.05 if i == 0 else 0.5,
                  "likely": "Toss-up (50%)", "detail": None} for i in range(10)]
        md = outlook.brief_markdown({"as_of": "2026-10-19T00:00:00+00:00", "forecasts": [], "headlines": [],
                                     "coming_up": items, "stock_moves": []})
        self.assertNotIn("Item 0", md)
        self.assertEqual(md.count("Toss-up"), outlook.BRIEF_ITEMS)
        self.assertIn("more items", md)


if __name__ == "__main__":
    unittest.main()
