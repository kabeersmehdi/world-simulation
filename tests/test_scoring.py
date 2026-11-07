import unittest
from datetime import datetime, timezone

from worldsim import scoring

from .helpers import good_forecast


def resolved(p, outcome, base=None, market=None, topic="military", fid="fc-r"):
    return good_forecast(
        id=fid, topic=topic, status="resolved",
        reference_class={"description": "A test reference class", "base_rate": base} if base is not None else None,
        history=[{"at": "2026-10-01T00:00:00+00:00", "probability": p, "rationale": "Scored test entry.", "benchmark_probability": market}],
        resolution={"outcome": outcome, "resolved_at": "2026-12-01T00:00:00+00:00", "source_url": "https://example.org"})


class ScoringTests(unittest.TestCase):
    def test_brier_known_values(self):
        self.assertAlmostEqual(scoring.brier(0.7, True), 0.09)
        self.assertAlmostEqual(scoring.brier(0.7, False), 0.49)
        self.assertEqual(scoring.brier(1.0, True), 0.0)

    def test_brier_rejects_bad_probability(self):
        with self.assertRaises(ValueError):
            scoring.brier(1.2, True)

    def test_uses_last_update_before_deadline(self):
        fc = resolved(0.2, True)
        fc["history"].append({"at": "2027-01-15T00:00:00+00:00", "probability": 0.98, "rationale": "After the deadline, ignored."})
        self.assertEqual(scoring.scored_probability(fc), 0.2)

    def test_scorecard_baselines_and_minimum(self):
        card = scoring.scorecard([resolved(0.8, True, base=0.5, market=0.6, fid="fc-a"), resolved(0.3, False, base=0.5, fid="fc-b")])
        self.assertEqual(card["resolved"], 2)
        self.assertFalse(card["enough_data"])
        self.assertAlmostEqual(card["mean_brier"], (0.04 + 0.09) / 2)
        self.assertAlmostEqual(card["vs_base_rate"]["baseline"], 0.25)
        self.assertEqual(card["vs_market"]["n"], 1)
        self.assertAlmostEqual(card["vs_market"]["baseline"], 0.16)

    def test_market_baseline_is_the_price_at_the_scored_update(self):
        fc = resolved(0.2, True, market=0.6)
        fc["history"].append({"at": "2026-11-01T00:00:00+00:00", "probability": 0.7, "rationale": "Later update, same-time market.", "benchmark_probability": 0.65})
        card = scoring.scorecard([fc])
        self.assertAlmostEqual(card["vs_market"]["baseline"], (1 - 0.65) ** 2)
        self.assertAlmostEqual(card["vs_market_at_entry"]["baseline"], (1 - 0.6) ** 2)
        self.assertAlmostEqual(card["mean_brier"], (1 - 0.7) ** 2)

    def test_scorecard_splits_by_view(self):
        a = resolved(0.8, True, market=0.6, fid="fc-a")
        b = resolved(0.3, False, market=0.5, fid="fc-b")
        b["history"][0]["view"] = "independent"
        b["history"][0]["players"] = [{"actor": "ac-trump", "does": "Something specific in the scenario."}]
        card = scoring.scorecard([a, b])
        self.assertEqual(set(card["by_view"]), {"market", "independent"})
        self.assertEqual(card["by_view"]["independent"]["n"], 1)
        self.assertAlmostEqual(card["by_view"]["independent"]["ours"], 0.09)

    def test_calibration_bands(self):
        card = scoring.scorecard([resolved(0.85, True, fid="fc-a"), resolved(0.82, False, fid="fc-b")])
        band = next(b for b in card["calibration"] if b["band"] == "80-90%")
        self.assertEqual(band["count"], 2)
        self.assertAlmostEqual(band["observed_rate"], 0.5)

    def test_enough_data_flag_at_twenty(self):
        card = scoring.scorecard([resolved(0.6, True, fid=f"fc-{i}") for i in range(20)])
        self.assertTrue(card["enough_data"])

    def test_overdue(self):
        now = datetime(2027, 2, 1, tzinfo=timezone.utc)
        self.assertEqual(scoring.overdue([good_forecast()], now), ["fc-test"])


if __name__ == "__main__":
    unittest.main()
