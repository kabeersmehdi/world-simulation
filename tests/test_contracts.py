import unittest

from worldsim.contracts import ContractError, errors_for, parse_datetime, validate

from .helpers import good_forecast


class ContractTests(unittest.TestCase):
    def test_good_forecast_passes(self):
        validate(good_forecast(), "forecast")

    def test_missing_field_fails_loud(self):
        fc = good_forecast()
        del fc["resolution_criteria"]
        with self.assertRaises(ContractError) as ctx:
            validate(fc, "forecast")
        self.assertIn("resolution_criteria", str(ctx.exception))

    def test_unknown_field_rejected(self):
        self.assertTrue(errors_for(good_forecast(secret_note="x"), "forecast"))

    def test_probability_above_one_rejected_by_schema(self):
        fc = good_forecast(history=[{"at": "2026-10-01T00:00:00+00:00", "probability": 1.4, "rationale": "Too confident by far."}])
        self.assertTrue(any("maximum" in e for e in errors_for(fc, "forecast")))

    def test_date_time_needs_timezone(self):
        with self.assertRaises(ValueError):
            parse_datetime("2026-10-01T00:00:00")
        self.assertTrue(errors_for(good_forecast(created_at="2026-10-01"), "forecast"))

    def test_evidence_needs_a_source(self):
        ev = {"id": "ev-x", "claim": "A claim with no source attached.", "label": "established_fact",
              "countries": ["israel"], "confidence": "high", "sources": [], "recorded_at": "2026-10-18T00:00:00+00:00"}
        self.assertTrue(any("at least 1" in e for e in errors_for(ev, "evidence")))

    def test_evidence_label_must_be_known(self):
        ev = {"id": "ev-x", "claim": "A claim with a made-up label.", "label": "obviously_true",
              "countries": ["israel"], "confidence": "high", "recorded_at": "2026-10-18T00:00:00+00:00",
              "sources": [{"url": "https://example.org", "publisher": "Example", "accessed_at": "2026-10-18", "kind": "official"}]}
        self.assertTrue(errors_for(ev, "evidence"))


if __name__ == "__main__":
    unittest.main()
