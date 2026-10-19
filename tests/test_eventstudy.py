import json
import unittest
from datetime import date, timedelta

from worldsim import eventstudy, prices

from .helpers import isolated_root


def chart(rows):
    """Fake Yahoo chart JSON from [(YYYY-MM-DD, close)]; gmtoffset 0."""
    from datetime import datetime, timezone
    ts = [int(datetime.fromisoformat(d).replace(tzinfo=timezone.utc).timestamp()) for d, _ in rows]
    return json.dumps({"chart": {"result": [{"meta": {"gmtoffset": 0}, "timestamp": ts,
                                              "indicators": {"quote": [{"close": [c for _, c in rows]}]}}]}})


def trading_days(start, n, price_fn):
    out, d = [], date.fromisoformat(start)
    while len(out) < n:
        if d.weekday() < 5:
            out.append((d.isoformat(), price_fn(len(out))))
        d += timedelta(days=1)
    return out


class EventStudyTests(unittest.TestCase):
    def test_parse_chart_skips_empty_days(self):
        rows = prices.parse_chart(chart([("2026-01-05", 10.0), ("2026-01-06", None), ("2026-01-07", 11.0)]))
        self.assertEqual(rows, [("2026-01-05", 10.0), ("2026-01-07", 11.0)])

    def test_move_uses_close_before_event(self):
        rows = [("2026-01-02", 100.0), ("2026-01-05", 110.0), ("2026-01-06", 121.0)]
        self.assertAlmostEqual(eventstudy.move(rows, "2026-01-03", 1), 10.0)   # Saturday event -> Monday close
        self.assertAlmostEqual(eventstudy.move(rows, "2026-01-03", 2), 21.0)
        self.assertIsNone(eventstudy.move(rows, "2026-01-02", 1))               # no close before
        self.assertIsNone(eventstudy.move(rows, "2026-01-05", 5))               # window runs off the end

    def test_run_offline_flags_and_robustness(self):
        root = isolated_root()
        (root / "config" / "assets.json").write_text(json.dumps({"history_start": "2023-09-01", "assets": [
            {"ticker": "OIL", "name": "Oil", "category": "commodity", "why": "test"},
            {"ticker": "DEF", "name": "Defense", "category": "equity", "why": "test", "benchmark": "SPY"},
            {"ticker": "SPY", "name": "SPY", "category": "index", "why": "test"}]}))
        events = {e["date"] for e in eventstudy.load_events(root)}
        base = trading_days("2023-09-01", 900, lambda i: 100.0 * (1 + 0.004 * ((-1) ** i)))
        def bump(rows, size):  # jump on each event day, flat otherwise
            out, level = [], 1.0
            for d, c in rows:
                if d in events or any(e <= d and prices.first_index_on_or_after(rows, e) == len(out) for e in events):
                    level *= 1 + size
                out.append((d, c * level))
            return out
        files = {"OIL": bump(base, 0.03), "DEF": bump(base, 0.02), "SPY": base}
        def fetch(url):
            t = url.split("/chart/")[1].split("?")[0]
            return chart(files[t])
        report = prices.collect(root, fetch=fetch)
        self.assertTrue(all(r["ok"] for r in report))
        res = eventstudy.run(root)
        self.assertEqual(len({e["date"] for e in res["events"]}), len(res["events"]))  # same-date events count once
        oil = next(a for a in res["assets"] if a["ticker"] == "OIL")["summary"]["1"]
        self.assertTrue(oil["unusual"])
        self.assertTrue(oil["holds_without_largest"])
        d = next(a for a in res["assets"] if a["ticker"] == "DEF")["summary"]["1"]
        self.assertEqual(d["measure"], "vs SPY")
        self.assertGreater(d["mean"], 1.0)
        self.assertIsNotNone(eventstudy.load(root))

    def test_one_event_carrying_the_average_does_not_hold(self):
        self.assertFalse(eventstudy.holds({"unusual": True, "mean": 5.0, "mean_without_largest": 0.5}))
        self.assertFalse(eventstudy.holds({"unusual": True, "mean": 5.0, "mean_without_largest": -3.0}))
        self.assertFalse(eventstudy.holds({"unusual": False, "mean": 5.0, "mean_without_largest": 4.0}))
        self.assertTrue(eventstudy.holds({"unusual": True, "mean": 5.0, "mean_without_largest": 2.5}))


if __name__ == "__main__":
    unittest.main()
