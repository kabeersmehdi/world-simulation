"""Red-team tests: each guard gets a bad record and must reject it."""

import copy
import unittest

from worldsim import forecasts as F

from .helpers import good_forecast, isolated_root, write_json


class GuardTests(unittest.TestCase):
    def test_good_forecast_passes_every_guard(self):
        F.check(good_forecast(), live=True)

    def test_rejects_zero_and_hundred_percent(self):
        for p in (0.0, 1.0, 0.995):
            fc = good_forecast(history=[{"at": "2026-10-01T00:00:00+00:00", "probability": p, "rationale": "False certainty."}])
            with self.assertRaises(F.GuardError):
                F.guard_probability_bounds(fc)

    def test_rejects_deadline_before_creation(self):
        with self.assertRaises(F.GuardError):
            F.guard_deadline_after_creation(good_forecast(deadline="2026-09-01T00:00:00+00:00"))

    def test_rejects_update_before_creation(self):
        fc = good_forecast(history=[{"at": "2026-09-01T00:00:00+00:00", "probability": 0.4, "rationale": "Dated before creation."}])
        with self.assertRaises(F.GuardError):
            F.guard_history_order(fc)

    def test_rejects_out_of_order_history(self):
        fc = good_forecast(history=[
            {"at": "2026-10-05T00:00:00+00:00", "probability": 0.4, "rationale": "Second update first."},
            {"at": "2026-10-02T00:00:00+00:00", "probability": 0.5, "rationale": "Earlier update second."}])
        with self.assertRaises(F.GuardError):
            F.guard_history_order(fc)

    def test_rejects_hindsight_edit(self):
        old = good_forecast()
        new = copy.deepcopy(old)
        new["history"][0]["probability"] = 0.9
        with self.assertRaises(F.GuardError):
            F.guard_append_only(old, new)

    def test_rejects_changed_question(self):
        old = good_forecast()
        with self.assertRaises(F.GuardError):
            F.guard_append_only(old, good_forecast(question="Will a different event happen instead?"))

    def test_allows_appended_update(self):
        old = good_forecast()
        new = copy.deepcopy(old)
        new["history"].append({"at": "2026-10-10T00:00:00+00:00", "probability": 0.5, "rationale": "New evidence came in."})
        F.guard_append_only(old, new)

    def test_rejects_resolved_without_source(self):
        with self.assertRaises(F.GuardError):
            F.guard_resolution(good_forecast(status="resolved"))

    def test_rejects_open_with_resolution(self):
        res = {"outcome": True, "resolved_at": "2026-11-01T00:00:00+00:00", "source_url": "https://example.org"}
        with self.assertRaises(F.GuardError):
            F.guard_resolution(good_forecast(resolution=res))

    def test_rejects_illustrative_in_live_folder(self):
        with self.assertRaises(F.GuardError):
            F.guard_no_illustrative_in_live(good_forecast(illustrative=True), live=True)

    def test_rejects_unlabeled_demo(self):
        with self.assertRaises(F.GuardError):
            F.guard_no_illustrative_in_live(good_forecast(), live=False)

    def test_new_forecast_skeleton_fails_until_filled(self):
        fc = good_forecast(history=[{"at": "2026-10-01T00:00:00+00:00", "probability": -1, "rationale": "WRITE THIS: why this number."}])
        with self.assertRaises(Exception):
            F.check(fc, live=True)

    def test_folder_load_uses_isolated_root(self):
        root = isolated_root()
        write_json(root / "data" / "forecasts" / "fc-test.json", good_forecast())
        live, demo = F.load_all(root)
        self.assertEqual([f["id"] for f in live], ["fc-test"])
        self.assertTrue(all(f["illustrative"] for f in demo))


if __name__ == "__main__":
    unittest.main()
