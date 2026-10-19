import unittest

from worldsim import signals


class SignalTests(unittest.TestCase):
    def test_hebrew_prefix_still_matches(self):
        self.assertEqual(signals.indicators_for("ופיקוד העורף הודיע"), ["home_front"])

    def test_tzav_8_is_reserves(self):
        self.assertIn("reserves", signals.indicators_for("צו 8 לאלפי לוחמים"))

    def test_cabinet_only_counts_late_at_night(self):
        late = "2026-10-18T20:40:00+00:00"   # 23:40 Israel time
        noon = "2026-10-18T09:00:00+00:00"   # 12:00 Israel time
        self.assertIn("late_night_cabinet", signals.indicators_for("הקבינט מתכנס", late))
        self.assertNotIn("late_night_cabinet", signals.indicators_for("הקבינט מתכנס", noon))
        self.assertNotIn("late_night_cabinet", signals.indicators_for("הקבינט מתכנס", None))

    def test_late_night_edges(self):
        self.assertTrue(signals.is_late_night("2026-10-18T18:00:00+00:00"))   # 21:00 Israel
        self.assertTrue(signals.is_late_night("2026-10-19T01:59:00+00:00"))   # 04:59 Israel
        self.assertFalse(signals.is_late_night("2026-10-19T02:00:00+00:00"))  # 05:00 Israel

    def test_allowed_limits_indicators(self):
        self.assertEqual(signals.indicators_for("Home Front Command ordered departure", allowed={"us_advisory"}), ["us_advisory"])

    def test_english_is_case_insensitive(self):
        self.assertIn("airspace", signals.indicators_for("Jordan CLOSES AIRSPACE"))

    def test_topics(self):
        self.assertEqual(signals.topics_for("טראמפ על איראן"), ["iran", "united-states"])

    def test_ordinary_text_is_quiet(self):
        self.assertEqual(signals.indicators_for("מזג האוויר מחר: נאה"), [])


if __name__ == "__main__":
    unittest.main()
