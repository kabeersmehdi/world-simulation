import unittest

from worldsim import actors, forecasts

from .helpers import good_forecast, isolated_root, write_json


class ActorTests(unittest.TestCase):
    def test_every_card_loads_and_every_line_is_sourced_or_marked(self):
        cards = actors.load_all()
        self.assertGreaterEqual(len(cards), 6)
        self.assertEqual([l for c in cards for l in actors.unmarked_lines(c)], [])

    def test_unmarked_line_is_caught(self):
        card = {"id": "ac-x", "wants": ["Wants something with no source."], "fears": [], "constraints": [], "red_lines": []}
        self.assertEqual(len(actors.unmarked_lines(card)), 1)

    def test_independent_view_needs_a_known_player(self):
        entry = {"at": "2026-10-01T00:00:00+00:00", "probability": 0.4, "rationale": "Our own view, long enough to count.", "view": "independent"}
        with self.assertRaises(forecasts.GuardError):
            forecasts.guard_independent_view(good_forecast(history=[entry]), {"ac-trump"})
        entry["players"] = [{"actor": "ac-nobody", "does": "Something specific in the scenario."}]
        with self.assertRaises(forecasts.GuardError):
            forecasts.guard_independent_view(good_forecast(history=[entry]), {"ac-trump"})
        entry["players"] = [{"actor": "ac-trump", "does": "Something specific in the scenario."}]
        forecasts.guard_independent_view(good_forecast(history=[entry]), {"ac-trump"})

    def test_load_all_rejects_unknown_player_in_live_folder(self):
        root = isolated_root()
        (root / "data" / "actors").mkdir()
        entry = {"at": "2026-10-01T00:00:00+00:00", "probability": 0.4, "rationale": "Our own view, long enough to count.",
                 "view": "independent", "players": [{"actor": "ac-nobody", "does": "Something specific in the scenario."}]}
        write_json(root / "data" / "forecasts" / "fc-test.json", good_forecast(history=[entry]))
        with self.assertRaises(forecasts.GuardError):
            forecasts.load_all(root)


if __name__ == "__main__":
    unittest.main()
