import unittest
from datetime import date

from worldsim import timing

LADDER = {"id": "l", "title": "Test ceasefire", "kind": "survival", "event": "a strike",
          "steps": [{"date": "2026-10-31", "slug": "a"}, {"date": "2026-11-30", "slug": "b"}, {"date": "2026-12-31", "slug": "c"}]}
TODAY = date(2026, 10, 19)


class TimingTests(unittest.TestCase):
    def test_monotone_pools_violations(self):
        self.assertEqual(timing.monotone_increasing([0.1, 0.3, 0.2, 0.5]), [0.1, 0.25, 0.25, 0.5])
        self.assertEqual(timing.monotone_increasing([0.1, 0.2]), [0.1, 0.2])

    def test_survival_ladder_becomes_break_curve(self):
        c = timing.curve(LADDER, {"a": 0.9, "b": 0.7, "c": 0.4}, TODAY)
        self.assertAlmostEqual(c["rows"][0]["in_window"], 0.1)
        self.assertAlmostEqual(c["rows"][1]["in_window"], 0.2)
        self.assertAlmostEqual(c["rows"][2]["by_date"], 0.6)
        self.assertAlmostEqual(c["after_last"], 0.4)
        self.assertFalse(c["adjusted"])

    def test_median_interpolates(self):
        c = timing.curve(LADDER, {"a": 0.9, "b": 0.7, "c": 0.4}, TODAY)
        # crosses 50% two thirds of the way from 11/30 (30%) to 12/31 (60%)
        self.assertEqual(c["median_date"], "2026-12-21")

    def test_median_none_when_never_crossed(self):
        self.assertIsNone(timing.curve(LADDER, {"a": 0.95, "b": 0.9, "c": 0.8}, TODAY)["median_date"])

    def test_cumulative_ladder_and_smoothing(self):
        lad = {**LADDER, "kind": "cumulative"}
        c = timing.curve(lad, {"a": 0.2, "b": 0.1, "c": 0.5}, TODAY)
        self.assertTrue(c["adjusted"])
        self.assertTrue(all(b["in_window"] >= 0 for b in c["rows"]))

    def test_past_and_missing_steps_dropped(self):
        c = timing.curve(LADDER, {"a": 0.9, "c": 0.4}, date(2026, 11, 5))
        self.assertEqual([r["slug"] for r in c["rows"]], ["c"])

    def test_calibration_shrinks_toward_market(self):
        bands = [{"mean_price": 0.3, "happened": 0.3, "count": 1000}, {"mean_price": 0.8, "happened": 0.95, "count": 30}]
        self.assertAlmostEqual(timing.calibrate(0.3, bands), 0.3, places=3)
        self.assertAlmostEqual(timing.calibrate(0.8, bands), 0.875)  # halfway: 30 / (30 + 30)
        self.assertEqual(timing.calibrate(0.6, None), 0.6)

    def test_calibrated_columns_added(self):
        bands = [{"mean_price": 0.3, "happened": 0.3, "count": 100}, {"mean_price": 0.9, "happened": 1.0, "count": 100}]
        c = timing.with_calibration(timing.curve(LADDER, {"a": 0.9, "b": 0.7, "c": 0.4}, TODAY), bands)
        self.assertLess(c["rows"][0]["calibrated_by_date"], c["rows"][0]["by_date"])
        self.assertIn("median_date", c["calibrated"])


if __name__ == "__main__":
    unittest.main()
