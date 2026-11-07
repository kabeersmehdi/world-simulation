import json
import math
import unittest
from datetime import datetime, timedelta, timezone

from worldsim import fear, leadlag
from worldsim.collectors import adsb

from .helpers import isolated_root

T0 = datetime(2026, 1, 1, tzinfo=timezone.utc)


def days(n, start=T0):
    return [(start + timedelta(days=i)).date().isoformat() for i in range(n)]


def flat_series(n, value=20.0, spikes=()):
    """A gauge that wobbles within 1.5 normal swings, except on the spike days, where it jumps 40%."""
    rows, v = [], value
    for i, d in enumerate(days(n)):
        v = v * (1.4 if i in spikes else 1.0 + 0.001 * ((i * 7 % 5) - 2))
        rows.append((d, v))
    return rows


class FearTests(unittest.TestCase):
    def test_changes_are_differences_for_levels_and_log_returns_for_prices(self):
        rows = [("2026-01-01", 10.0), ("2026-01-02", 12.0)]
        self.assertAlmostEqual(fear.changes(rows, "level")[0][1], 2.0)
        self.assertAlmostEqual(fear.changes(rows, "price")[0][1], math.log(1.2))

    def test_firings_need_history_and_a_quiet_spell(self):
        rows = flat_series(200, spikes=(100, 102, 150))
        fired, calendar = fear.firings(rows, "price", "up", 1.5, 252, 60, 5)
        self.assertEqual([f["date"] for f in fired], [rows[100][0], rows[150][0]])  # day 102 is inside the quiet spell
        self.assertEqual(calendar[0], rows[61][0])  # the calendar starts once 60 changes are known

    def test_direction_down_fires_on_falls(self):
        rows = flat_series(200, spikes=(100,))
        fired, _ = fear.firings(rows, "price", "down", 1.5, 252, 60, 5)
        self.assertEqual(fired, [])

    def _market(self, jump_days, t0, hours=24 * 300):
        """Hourly Yes price that steps up 20 points an hour after each firing's close (inside the after window)."""
        history, p = [], 0.3
        jump_hours = {int((fear._close_ts(d, 21) - t0) // 3600) + 2 for d in jump_days}
        for h in range(hours):
            if h in jump_hours:
                p = min(p + 0.2, 0.95)
            elif h % 24 == 0:
                p = max(p - 0.01, 0.05)
            history.append({"t": t0 + h * 3600, "p": p})
        return leadlag.hourly(history, t0)

    def test_measure_finds_a_lead_when_the_crowd_moves_after_the_gauge(self):
        t0 = T0.timestamp()
        spikes = tuple(range(70, 270, 15))
        rows = flat_series(300, spikes=spikes)
        fired, calendar = fear.firings(rows, "price", "up", 1.5, 252, 60, 5)
        self.assertGreaterEqual(len(fired), 10)
        hist = [self._market([f["date"] for f in fired], t0)]
        res = fear.measure(fired, calendar, hist, [24], t0, t0 + 300 * 86400, 21, draws=200)
        row = res["horizons"]["24"]
        self.assertGreater(row["after_vs_random"], 2)
        self.assertLess(row["p_value"], 0.05)
        self.assertIn("moves before the market", leadlag.verdict(res, 0.05, 10))

    def test_measure_finds_nothing_when_the_crowd_ignores_the_gauge(self):
        t0 = T0.timestamp()
        spikes = tuple(range(70, 270, 15))
        rows = flat_series(300, spikes=spikes)
        fired, calendar = fear.firings(rows, "price", "up", 1.5, 252, 60, 5)
        other_days = [d for d in calendar if d not in {f["date"] for f in fired}][::9][:12]
        hist = [self._market(other_days, t0)]
        res = fear.measure(fired, calendar, hist, [24], t0, t0 + 300 * 86400, 21, draws=200)
        self.assertIn("no lead", leadlag.verdict(res, 0.05, 10))

    def test_series_builds_spread_and_ratio(self):
        root = isolated_root()
        (root / "data" / "prices").mkdir(parents=True)
        for t, v in (("BZ=F", 80.0), ("CL=F", 75.0)):
            (root / "data" / "prices" / (t.replace("=", "_") + ".json")).write_text(json.dumps({"ticker": t, "rows": [["2026-01-02", v], ["2026-01-05", v + 1]]}))
        self.assertEqual(fear.series({"spread": ["BZ=F", "CL=F"]}, root)[0][1], 5.0)
        self.assertAlmostEqual(fear.series({"ratio": ["BZ=F", "CL=F"]}, root)[1][1], 81 / 76)
        self.assertIsNone(fear.series({"ticker": "GC=F"}, root))


class AircraftLogTests(unittest.TestCase):
    def test_hourly_counts_are_logged_once_per_hour_zeros_included(self):
        root = isolated_root()
        source = {"id": "adsb-lol"}
        empty = json.dumps({"ac": []})
        tanker = json.dumps({"ac": [{"hex": "ae1", "t": "KC46", "lat": 30.0, "lon": 40.0, "flight": "RCH1"}]})
        self.assertEqual(adsb.collect(source, empty, "2026-11-07T10:05:00+00:00", root), [])
        adsb.collect(source, empty, "2026-11-07T10:20:00+00:00", root)
        obs = adsb.collect(source, tanker, "2026-11-07T11:05:00+00:00", root)
        self.assertEqual(len(obs), 1)
        lines = [json.loads(l) for l in (root / "data" / "signals" / "aircraft.jsonl").read_text().splitlines()]
        self.assertEqual([l["hour"] for l in lines], ["2026-11-07T10", "2026-11-07T11"])
        self.assertEqual(lines[0]["tanker"], 0)
        self.assertEqual(lines[1]["tanker"], 1)


if __name__ == "__main__":
    unittest.main()
