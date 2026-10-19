import unittest

from worldsim import baserates

from .helpers import isolated_root


def ref(events):
    return {"id": "br-test", "description": "Test reference class", "question_shape": "Will X respond within N days?",
            "inclusion_rule": "Only test events.", "events": events}


def ev(i, trig, resp):
    return {"id": i, "trigger_date": trig, "trigger": "Test trigger", "responded": resp is not None,
            "response_date": resp, "response": None, "verified": True, "sources": ["https://example.org"]}


class BaseRateTests(unittest.TestCase):
    def test_laplace_never_gives_certainty(self):
        self.assertAlmostEqual(baserates.laplace(3, 3), 0.8)
        self.assertAlmostEqual(baserates.laplace(0, 3), 0.2)

    def test_summary_lags_and_windows(self):
        s = baserates.summarize(ref([ev("a", "2024-01-01", "2024-01-03"), ev("b", "2024-02-01", "2024-02-21"), ev("c", "2024-03-01", None)]))
        self.assertEqual(s["events"], 3)
        self.assertAlmostEqual(s["response_rate"], 0.6)
        self.assertEqual(s["lag_days"], {"median": 11.0, "min": 2, "max": 20})
        self.assertAlmostEqual(s["chance_within_days"]["7"], 0.4)

    def test_small_sample_warning(self):
        s = baserates.summarize(ref([ev("a", "2024-01-01", "2024-01-03")]))
        self.assertTrue(s["small_sample"])
        self.assertIn("noise", s["warning"])

    def test_seed_file_loads_and_is_marked_small(self):
        rows = baserates.load_all(isolated_root())
        self.assertTrue(rows)
        self.assertTrue(all(r["small_sample"] for r in rows))


if __name__ == "__main__":
    unittest.main()
