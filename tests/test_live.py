import json
import subprocess
import unittest
from datetime import date, timedelta

from worldsim import live, prices

from .helpers import isolated_root


def yahoo(price, prev):
    return json.dumps({"chart": {"result": [{"meta": {"regularMarketPrice": price, "chartPreviousClose": prev}}]}})


def write_daily(root, ticker, closes):
    d = date(2025, 9, 1)
    rows = []
    for c in closes:
        rows.append((d.isoformat(), c))
        d += timedelta(days=1)
    path = prices._file(root, ticker)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"ticker": ticker, "rows": rows}))


class LiveTests(unittest.TestCase):
    def setUp(self):
        self.root = isolated_root()
        import shutil
        shutil.copy(live.ROOT / "config" / "live.json", self.root / "config" / "live.json")

    def test_yahoo_fallback_when_no_tool(self):
        snap = live.snapshot(self.root, fetch=lambda url: yahoo(110.0, 100.0), run=None)
        self.assertIn("Yahoo", snap["source"])
        self.assertEqual(len(snap["quotes"]), len(live.load_config(self.root)))
        self.assertAlmostEqual(snap["quotes"][0]["change_pct"], 10.0)
        self.assertIsNotNone(live.load(self.root))

    def test_tradingview_tool_is_run_as_a_separate_program(self):
        tool = self.root / "tool"
        (tool / "scripts").mkdir(parents=True)
        (tool / "scripts" / "snapshot_quotes.py").write_text("# fake")
        (tool / "config").mkdir()
        (tool / "config" / "watchlist.json").write_text(json.dumps({"timezone": "America/New_York", "history_plan": {}}))
        (self.root / "config" / "local.json").write_text(json.dumps({"tradingview_tool": str(tool), "tradingview_python": "py"}))
        seen = {}

        def fake_run(cmd, **kw):
            seen["cmd"] = cmd
            wl = json.loads(open(cmd[cmd.index("--symbols-file") + 1]).read())
            quotes = {s["tv_symbol"]: {"price": 50.0, "change_pct": 1.0, "freshness": "FRESH", "feed_delay_minutes": 0} for s in wl["symbols"]}
            return subprocess.CompletedProcess(cmd, 0, json.dumps({"snapshot_time_et": "x", "quotes": quotes, "data_quality": []}), "")
        snap = live.snapshot(self.root, fetch=None, run=fake_run)
        self.assertEqual(seen["cmd"][0], "py")
        self.assertTrue(seen["cmd"][1].endswith("snapshot_quotes.py"))
        self.assertIn("TradingView", snap["source"])

    def test_tool_failure_falls_back_to_yahoo(self):
        tool = self.root / "tool"
        (tool / "scripts").mkdir(parents=True)
        (tool / "scripts" / "snapshot_quotes.py").write_text("# fake")
        (tool / "config").mkdir()
        (tool / "config" / "watchlist.json").write_text(json.dumps({"timezone": "America/New_York", "history_plan": {}}))
        (self.root / "config" / "local.json").write_text(json.dumps({"tradingview_tool": str(tool)}))
        failing = lambda cmd, **kw: subprocess.CompletedProcess(cmd, 1, "", "boom")
        snap = live.snapshot(self.root, fetch=lambda url: yahoo(10.0, 10.0), run=failing)
        self.assertIn("TradingView tool failed", snap["source"])
        self.assertTrue(snap["quotes"])

    def test_stress_flags_and_level(self):
        flat = [100.0 + (i % 2) for i in range(300)]
        for t in ("BZ=F", "LMT", "RTX", "ESLT"):
            write_daily(self.root, t, flat)
        write_daily(self.root, "CL=F", [90.0] * 300)
        snap = {"quotes": [
            {"alias": "BRENT", "name": "Brent", "group": "Oil", "price": 120.0, "change_pct": 5.0},
            {"alias": "WTI", "name": "WTI", "group": "Oil", "price": 95.0, "change_pct": 1.0},
            {"alias": "LMT", "name": "LMT", "group": "Defense", "price": 1.0, "change_pct": 4.0},
            {"alias": "RTX", "name": "RTX", "group": "Defense", "price": 1.0, "change_pct": 4.0},
            {"alias": "ESLT", "name": "ESLT", "group": "Defense", "price": 1.0, "change_pct": 0.1}]}
        s = live.stress(snap, self.root)
        self.assertEqual(s["level"], "high stress")
        self.assertIn("the seaborne oil premium is wide", s["flags"])
        by = {q["alias"]: q for q in s["quotes"]}
        self.assertEqual(by["BRENT"]["size"], "very big move")
        self.assertEqual(by["ESLT"]["size"], "normal day")

    def test_percentile(self):
        self.assertEqual(live.percentile(5, [1, 2, 3, 4, 6]), 80)
        self.assertIsNone(live.percentile(5, []))


if __name__ == "__main__":
    unittest.main()
