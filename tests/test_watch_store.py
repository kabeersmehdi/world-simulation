import unittest
from datetime import timedelta

from worldsim import store
from worldsim.watch import level_for, watch_status

from .helpers import NOW, isolated_root


def ob(indicator, hours_ago, sid="src"):
    at = (NOW - timedelta(hours=hours_ago)).isoformat()
    return store.make_observation(collector="rss", source_id=sid, key=f"{indicator}{hours_ago}", observed_at=at,
                                  published_at=at, title="t", url="https://example.org", lang="he",
                                  indicators=[indicator], tags=[])


class WatchTests(unittest.TestCase):
    def test_levels(self):
        self.assertEqual([level_for(n) for n in range(5)], ["baseline", "baseline", "elevated", "high", "high"])

    def test_counts_distinct_indicators_inside_windows(self):
        status = watch_status([ob("home_front", 2), ob("home_front", 3), ob("reserves", 10), ob("airspace", 60)], NOW)
        self.assertEqual(status["active_count"], 2)
        self.assertEqual(status["level"], "elevated")
        self.assertFalse(status["indicators"]["airspace"]["active"])
        self.assertFalse(status["calibrated"])

    def test_fleet_window_is_longer(self):
        self.assertTrue(watch_status([ob("us_military_moves", 150)], NOW)["indicators"]["us_military_moves"]["active"])

    def test_future_items_ignored(self):
        self.assertEqual(watch_status([ob("reserves", -5)], NOW)["active_count"], 0)


class StoreTests(unittest.TestCase):
    def test_save_dedupes_and_loads(self):
        root = isolated_root()
        items = [ob("reserves", 1), ob("reserves", 1), ob("airspace", 30)]
        self.assertEqual(store.save(items, root), 2)
        self.assertEqual(store.save(items, root), 0)
        self.assertEqual(len(store.load(root, days=7, now=NOW)), 2)


if __name__ == "__main__":
    unittest.main()
