import unittest

from worldsim import calibration


def rows(n=60, closed="2026-05-01"):
    """Long shots priced at 5% that happen 2% of the time, plus sure things priced 95% that always happen."""
    out = []
    for i in range(n):
        out.append({"closed": closed, "outcome": i % 50 == 0, "p30": 0.05, "p7": 0.05, "p1": 0.05})
        out.append({"closed": closed, "outcome": True, "p30": 0.95, "p7": 0.95, "p1": 0.95})
    return out


class CalibrationTests(unittest.TestCase):
    def test_pav_is_a_rising_staircase(self):
        steps = calibration.pav([(0.1, True), (0.2, False), (0.3, False), (0.9, True)])
        rates = [s[2] for s in steps]
        self.assertEqual(rates, sorted(rates))
        self.assertEqual(sum(s[3] for s in steps), 4)

    def test_horizon_picks_map_by_days_and_switches_off_at_the_ends(self):
        self.assertEqual(calibration.horizon_for(30), "30")
        self.assertEqual(calibration.horizon_for(14), "30")
        self.assertEqual(calibration.horizon_for(5), "7")
        self.assertIsNone(calibration.horizon_for(1))
        self.assertIsNone(calibration.horizon_for(calibration.MAX_DAYS + 1))

    def test_adjust_moves_long_shots_toward_what_happened(self):
        model = calibration.fit(rows())
        self.assertLess(calibration.adjust(0.05, 20, model), 0.05)
        self.assertGreaterEqual(calibration.adjust(0.05, 20, model), calibration.FLOOR)
        self.assertEqual(calibration.adjust(0.05, 1, model), 0.05)  # last two days: untouched

    def test_adjust_without_a_model_returns_the_price(self):
        self.assertEqual(calibration.adjust(0.3, 20, None), 0.3)
        self.assertEqual(calibration.adjust(0.3, 20, {"30": {"steps": []}}), 0.3)

    def test_check_fits_before_cutoff_and_scores_after(self):
        data = rows(closed="2026-05-01") + rows(n=20, closed="2026-09-01")
        out = calibration.check(data, cutoff="2026-08-01")
        self.assertEqual(out["train_markets"], 120)
        self.assertEqual(out["test_markets"], 40)
        self.assertTrue(out["horizons"]["30"]["helps"])
        self.assertFalse(out["horizons"]["1"]["helps"])

    def test_small_samples_fit_nothing(self):
        model = calibration.fit(rows(n=3))
        self.assertEqual(model["30"]["steps"], [])


if __name__ == "__main__":
    unittest.main()
