import json
import unittest
from datetime import datetime, timezone

from worldsim import backfill, backtest, leadlag

from .helpers import fixture, isolated_root, write_json

H = 3600
SINCE = datetime(2026, 1, 1, tzinfo=timezone.utc).timestamp()


def iso(t):
    return datetime.fromtimestamp(t, timezone.utc).isoformat()


def stepped_market(jumps, hours=1000, start=0.5, size=0.1):
    """Hourly prices from SINCE that step by `size` (alternating up and down) at the given hours."""
    p, out, sign = start, [], 1
    jumps = set(jumps)
    for i in range(hours):
        if i in jumps:
            p += sign * size
            sign = -sign
        out.append({"t": SINCE + i * H, "p": round(p, 4)})
    return out


ONSET_HOURS = [50 + 60 * k for k in range(15)]


class OnsetTests(unittest.TestCase):
    def test_quiet_gap_collapses_bursts(self):
        firings = [{"source_id": "s", "at": iso(SINCE + h * H), "indicators": ["home_front"]} for h in (0, 1, 30, 60, 200)]
        got = leadlag.onsets(firings, quiet_hours=48)["home_front"]
        # 0 starts a burst; 1, 30 and 60 each sit within 48 hours of the firing before; 200 is new.
        self.assertEqual([t for t, _ in got], [SINCE, SINCE + 200 * H])

    def test_hourly_forward_fills(self):
        grid = leadlag.hourly([{"t": SINCE + 10, "p": 0.2}, {"t": SINCE + 2 * H + 5, "p": 0.6}, {"t": SINCE + 4 * H, "p": 0.7}], SINCE)
        self.assertEqual(grid, (1, [0.2, 0.2, 0.6, 0.7]))
        self.assertIsNone(leadlag.hourly([{"t": SINCE, "p": 0.5}], SINCE))


class MeasureTests(unittest.TestCase):
    def run_case(self, jump_offset):
        hist = stepped_market([h + jump_offset for h in ONSET_HOURS])
        grids = [leadlag.hourly(hist, SINCE)]
        onset_list = [(SINCE + h * H + 600, "s") for h in ONSET_HOURS]
        res = leadlag.measure(onset_list, grids, {"s": (SINCE, SINCE + 999 * H)}, [6], SINCE, SINCE + 999 * H, draws=300)
        res["verdict"] = leadlag.verdict(res)
        return res

    def test_jump_after_the_onset_is_a_lead(self):
        res = self.run_case(+3)
        row = res["horizons"]["6"]
        self.assertAlmostEqual(row["mean_move_after"], 0.1)
        self.assertAlmostEqual(row["mean_move_before"], 0.0)
        self.assertLess(row["p_value"], 0.01)
        self.assertGreater(row["after_vs_random"], 3)
        self.assertTrue(res["verdict"].startswith("moves before the market"), res["verdict"])

    def test_jump_before_the_onset_is_not_a_lead(self):
        res = self.run_case(-3)
        row = res["horizons"]["6"]
        self.assertAlmostEqual(row["mean_move_after"], 0.0)
        self.assertLess(row["p_value_before"], 0.01)
        self.assertTrue(res["verdict"].startswith("no lead"), res["verdict"])

    def test_move_inside_the_onset_hour_does_not_count(self):
        # The jump lands in the same hour as the firing: too fast to trade on.
        res = self.run_case(+1)
        self.assertAlmostEqual(res["horizons"]["6"]["mean_move_after"], 0.0)

    def test_one_big_event_is_flagged(self):
        # A long, quiet market with one jump right after the first onset.
        hist = stepped_market([ONSET_HOURS[0] + 3], hours=20000, size=0.4)
        grids = [leadlag.hourly(hist, SINCE)]
        onset_list = [(SINCE + h * H + 600, "s") for h in ONSET_HOURS]
        end = SINCE + 19999 * H
        res = leadlag.measure(onset_list, grids, {"s": (SINCE, end)}, [6], SINCE, end, draws=300)
        self.assertLess(res["horizons"]["6"]["p_value"], 0.05)
        self.assertTrue(leadlag.verdict(res).startswith("one event only"), leadlag.verdict(res))

    def test_quiet_market_has_no_lead(self):
        grids = [leadlag.hourly(stepped_market([]), SINCE)]
        onset_list = [(SINCE + h * H, "s") for h in ONSET_HOURS]
        res = leadlag.measure(onset_list, grids, {"s": (SINCE, SINCE + 999 * H)}, [6], SINCE, SINCE + 999 * H, draws=50)
        self.assertTrue(leadlag.verdict(res).startswith("no lead"))

    def test_few_onsets_are_not_judged(self):
        grids = [leadlag.hourly(stepped_market([53, 113]), SINCE)]
        res = leadlag.measure([(SINCE + 50 * H, "s"), (SINCE + 110 * H, "s")], grids, {"s": (SINCE, SINCE + 999 * H)}, [6], SINCE, SINCE + 999 * H, draws=50)
        self.assertTrue(leadlag.verdict(res).startswith("too few onsets"))


def fake_fetch(url):
    if "gamma-api" in url:
        slug = url.split("slug=")[1].split("&")[0]
        return json.dumps([{"question": slug, "clobTokenIds": json.dumps([f"tok-{slug}", "no"]), "volumeNum": 1000,
                            "startDate": iso(SINCE), "closed": False}])
    start = int(url.split("startTs=")[1].split("&")[0])
    end = int(url.split("endTs=")[1].split("&")[0])
    hist = [p for p in stepped_market([h + 3 for h in ONSET_HOURS]) if start <= p["t"] <= end]
    # Like the real API, add today's price on the end of every answer.
    return json.dumps({"history": hist + [{"t": SINCE + 5000 * H, "p": 0.99}]})


class RunTests(unittest.TestCase):
    def test_price_history_ends_on_a_fractional_time(self):
        calls = []

        def fetch(url):
            calls.append(url)
            return fake_fetch(url)

        hist = leadlag.price_history("tok", SINCE, SINCE + 25 * 86400 + 0.5, fetch, pause=0)
        self.assertEqual(len(calls), 3)
        self.assertEqual(hist[-1]["t"], SINCE + 600 * H)

    def test_offline_run(self):
        root = isolated_root()
        cfg = json.loads((root / "config" / "leadlag.json").read_text())
        cfg.update({"random_draws": 100, "horizons": [6], "from_backtest": None})
        write_json(root / "config" / "leadlag.json", cfg)
        write_json(root / "config" / "markets.json", {"markets": [
            {"slug": "war-market", "label": "x", "countries": ["iran"], "topic": "military", "outcome_index": 0},
            {"slug": "vote-market", "label": "y", "countries": ["israel"], "topic": "election", "outcome_index": 0}]})
        firings = [{"source_id": "tg-test", "key": str(h), "at": iso(SINCE + h * H + 60), "indicators": ["home_front"]} for h in ONSET_HOURS]
        (root / "data" / "backfill").mkdir(parents=True)
        (root / "data" / "backfill" / "firings.jsonl").write_text("".join(json.dumps(f) + "\n" for f in firings))
        write_json(root / "data" / "backfill" / "coverage.json",
                   {"sources": [{"source_id": "tg-test", "from": iso(SINCE), "to": iso(SINCE + 999 * H)}]})
        now = datetime.fromtimestamp(SINCE + 999 * H, timezone.utc)
        r = leadlag.run(root, fetch=fake_fetch, now=now, log=lambda *_: None)
        self.assertEqual(r["markets"]["total"], 1)  # the election market is left out
        self.assertEqual(r["indicators"]["home_front"]["onsets"], 15)
        self.assertTrue(r["indicators"]["home_front"]["verdict"].startswith("moves before"))
        self.assertEqual(r["indicators"]["airspace"]["onsets"], 0)
        cached = json.loads((root / "data" / "leadlag" / "prices" / "war-market.json").read_text())
        self.assertLess(cached["history"][-1]["t"], SINCE + 5000 * H)  # the tacked-on point is dropped
        self.assertTrue((root / "data" / "leadlag" / "result.json").exists())


class BackfillTests(unittest.TestCase):
    def test_telegram_pages_back_until_since(self):
        page = fixture("telegram.html")
        calls = []

        def fetch(url):
            calls.append(url)
            return page

        posts = __import__("worldsim.collectors.telegram", fromlist=["parse"]).parse(page)
        oldest = min(datetime.fromisoformat(p["published_at"]) for p in posts)
        firings, cov = backfill.telegram_history({"id": "tg-kann-news", "url": "https://t.me/s/kann_news"}, oldest, fetch, max_pages=5, pause=0)
        self.assertEqual(calls[0], "https://t.me/s/kann_news")
        self.assertIn("?before=5001", calls[1])
        self.assertEqual(len(calls), 2)  # the second page did not move back, so it stops
        self.assertEqual(cov["posts"], len(posts))
        self.assertTrue(all("text" not in f for f in firings))  # no post text is kept

    def test_advisory_firings_keep_departures_only(self):
        got = backfill.advisory_firings(fixture("advisories.xml"))
        self.assertEqual([(f["country"], f["level"]) for f in got], [("Israel", 3)])
        self.assertEqual(got[0]["indicators"], ["us_advisory"])

    def test_advisory_history_dedupes_across_copies(self):
        xml = fixture("advisories.xml")
        cdx = json.dumps([["urlkey", "timestamp"], ["k", "20261018010000"], ["k", "20261018120000"], ["k", "20261019010000"]])
        fetched = []

        def fetch(url):
            fetched.append(url)
            return cdx if "cdx" in url else xml

        firings, cov = backfill.advisory_history(datetime(2026, 10, 1, tzinfo=timezone.utc), fetch, pause=0)
        self.assertEqual(len(firings), 1)
        self.assertEqual(cov["copies"], 2)  # one copy per day
        self.assertEqual(len(fetched), 3)


def row(volume, p7, outcome, event):
    return {"slug": f"{event}-{volume}-{p7}", "question": "q", "event": event, "closed": "2026-09-01",
            "outcome": outcome, "volume": volume, "p30": None, "p7": p7, "p1": p7}


class VolumeSplitTests(unittest.TestCase):
    def test_calibration_error(self):
        rows = [row(1, 0.25, False, "a"), row(1, 0.25, True, "b"), row(1, 0.95, True, "c")]
        # Band 20-30%: price 0.25, happened 0.5 -> gap 0.25 on 2 rows; band 90-100%: gap 0.05 on 1 row.
        self.assertAlmostEqual(backtest.calibration_error(rows, 7), (2 * 0.25 + 0.05) / 3)

    def test_thin_long_shots_overpriced(self):
        thin = [row(10 + i, 0.2, False, f"t{i}") for i in range(20)]
        thick = [row(10**6 + i, 0.2, i % 5 == 0, f"k{i}") for i in range(20)]
        out = backtest.by_volume(thin + thick, buckets=2, draws=200)
        self.assertEqual([b["markets"] for b in out["buckets"]], [20, 20])
        self.assertAlmostEqual(out["buckets"][0]["horizons"]["7"]["longshot_gap"], 0.2)
        self.assertAlmostEqual(out["buckets"][1]["horizons"]["7"]["longshot_gap"], 0.0)
        c = out["thin_vs_thick"]["7"]
        self.assertAlmostEqual(c["longshot_gap_diff"], 0.2)
        self.assertGreater(c["longshot_gap_ci"][0], 0)
        self.assertIsNone(out["thin_vs_thick"]["30"])

    def test_from_file_writes_split(self):
        root = isolated_root()
        rows = [row(10 + i, 0.2, i % 4 == 0, f"e{i}") for i in range(40)]
        write_json(root / "data" / "backtests" / "polymarket-geopolitics.json", {"run_at": "x", "min_volume": 1, "rows": rows})
        self.assertEqual(len(backtest.by_volume_from_file(root)["buckets"]), 4)
        self.assertTrue((root / "data" / "backtests" / "by-volume.json").exists())


if __name__ == "__main__":
    unittest.main()
