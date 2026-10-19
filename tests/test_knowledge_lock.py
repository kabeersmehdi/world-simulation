"""Locks the OKF knowledge files to the code so docs and constants can never drift."""

import re
import unittest

from worldsim import ROOT, signals, watch
from worldsim.build import read_frontmatter
from worldsim import collectors
from worldsim.collectors import adsb, firms, gpsjam

DOC = (ROOT / "docs" / "indicators.md").read_text(encoding="utf-8")


def table_rows(text, header_start):
    section = text.split(header_start, 1)[1]
    rows = []
    for line in section.splitlines()[2:]:
        if not line.startswith("|"):
            break
        rows.append([c.strip() for c in line.strip("|").split("|")])
    return rows


class KnowledgeLockTests(unittest.TestCase):
    def test_keywords_match_doc(self):
        doc_pairs = {(r[0], r[1]) for r in table_rows(DOC, "| Indicator | Keyword |")}
        code_pairs = {(k, w) for k, words in signals.INDICATOR_KEYWORDS.items() for w in words}
        self.assertEqual(doc_pairs, code_pairs)

    def test_windows_match_doc(self):
        rows = table_rows(DOC, "| Indicator | What it is |")
        doc = {r[0].strip("`"): int(r[3]) for r in rows}
        self.assertEqual(doc, watch.WINDOW_HOURS)

    def test_gps_thresholds_match_doc(self):
        doc = {r[0]: r[1] for r in table_rows(DOC, "| Setting | Value |")}
        self.assertEqual(doc, {
            "Degraded below NACp": str(gpsjam.DEGRADED_BELOW_NACP),
            "Minimum aircraft reporting": str(gpsjam.MIN_REPORTING),
            "Minimum degraded aircraft": str(gpsjam.MIN_DEGRADED),
            "Minimum degraded share": f"{gpsjam.MIN_DEGRADED_SHARE:.0%}",
        })

    def test_firms_rules_and_sites_match_doc(self):
        rules = {r[0]: (int(r[1]), float(r[2])) for r in table_rows(DOC, "| Site kind | Minimum solid detections |")}
        self.assertEqual(rules, firms.RULES)
        doc_sites = {r[0]: (r[1], r[2], float(r[3]), r[4]) for r in table_rows(DOC, "| Site | Name | Lat, lon |")}
        code_sites = {s["id"]: (s["name"], f"{s['lat']}, {s['lon']}", float(s["radius_km"]), s["kind"])
                      for src in collectors.load_sources(ROOT)["sources"] if src["kind"] == "firms" for s in src["sites"]}
        self.assertEqual(doc_sites, code_sites)
        self.assertTrue(all(s[3] in firms.RULES for s in code_sites.values()))

    def test_aircraft_classes_match_doc(self):
        doc = {r[0]: [c.strip() for c in r[1].split(",")] for r in table_rows(DOC, "| Class | Type codes |")}
        self.assertEqual(doc, adsb.AIRCRAFT_CLASSES)
        self.assertIn(f"at least {adsb.MIN_AIRCRAFT_FOR_INDICATOR} of these", DOC)

    def test_levels_match_doc(self):
        self.assertEqual(table_rows(DOC, "| Distinct indicators active | Level |"),
                         [["0 to 1", "baseline"], ["2", "elevated"], ["3 or more", "high"]])
        self.assertEqual(watch.LEVELS, [(3, "high"), (2, "elevated"), (0, "baseline")])

    def test_late_night_hours_match_doc(self):
        self.assertIn(f"between {signals.LATE_NIGHT_START_HOUR}:00 and 0{signals.LATE_NIGHT_END_HOUR}:00 Israel time", DOC)

    def test_every_markdown_file_has_okf_type(self):
        files = [p for p in ROOT.rglob("*.md") if ".git" not in p.parts and p.name != "README.md"]
        self.assertTrue(files)
        for path in files:
            meta, _ = read_frontmatter(path)
            self.assertIn("type", meta, f"{path} has no OKF type")

    def test_index_declares_okf_version(self):
        meta, body = read_frontmatter(ROOT / "index.md")
        self.assertEqual(meta["okf_version"], "0.2")
        for target in re.findall(r"\]\(([^)]+\.md)\)", body):
            self.assertTrue((ROOT / target).exists(), f"index links to missing {target}")

    def test_forecasting_minimum_matches_doc(self):
        from worldsim.scoring import MIN_RESOLVED_FOR_CLAIMS
        self.assertIn(f"at least {MIN_RESOLVED_FOR_CLAIMS} forecasts", (ROOT / "docs" / "forecasting-policy.md").read_text())

    def test_timing_constants_match_doc(self):
        from worldsim import backtest, timing
        doc = (ROOT / "docs" / "timing-and-accuracy.md").read_text()
        self.assertIn(f"`SHRINK = {timing.SHRINK}`", doc)
        self.assertIn(f"within {backtest.SETTLED} of 0 or 1", doc)
        self.assertIn(", ".join(str(h) for h in backtest.HORIZONS[:2]) + f" and {backtest.HORIZONS[2]} days", doc)

    def test_event_study_constants_match_doc(self):
        from worldsim import eventstudy
        doc = (ROOT / "docs" / "event-study.md").read_text()
        self.assertIn(f"at least {eventstudy.UNUSUAL_Z} standard errors", doc)
        self.assertIn(f"`ROBUST_SHARE = {eventstudy.ROBUST_SHARE}`", doc)
        self.assertIn("windows of " + ", ".join(str(w) for w in eventstudy.WINDOWS[:-1]) + f" and {eventstudy.WINDOWS[-1]} trading days", doc)

    def test_outlook_words_match_doc(self):
        from worldsim import outlook
        doc = (ROOT / "docs" / "outlook.md").read_text()
        rows = table_rows(doc, "| Chance | Verdict |")
        self.assertEqual([r[1] for r in rows], [w for _, w in outlook.VERDICTS])
        for (floor, _), r in zip(outlook.VERDICTS[:-1], rows):
            self.assertIn(str(round(floor * 100)), r[0])
        self.assertIn(f"Within {outlook.GAP_POINTS} points", doc)
        self.assertIn(f"under {round(outlook.BRIEF_MIN * 100)}%", doc)
        self.assertIn(f"at most {outlook.BRIEF_ITEMS}", doc)

    def test_markets_now_constants_match_doc(self):
        from worldsim import live
        doc = (ROOT / "docs" / "markets-now.md").read_text()
        self.assertIn(f"{live.BIG_MOVE} swings or more is a big move", doc)
        self.assertIn(f"{live.VERY_BIG_MOVE} or more a very big move", doc)
        self.assertIn(f"higher than {live.HIGH_PERCENTILE}% of the past year counts as high", doc)
        self.assertEqual(live.STRESS_LEVELS, [(3, "high stress"), (1, "some stress"), (0, "calm")])
        self.assertIn("0 flags is calm, 1 or 2 is some stress, 3 or more is high stress", doc)

    def test_small_sample_matches_doc(self):
        from worldsim.baserates import SMALL_SAMPLE
        self.assertIn(f"Fewer than {SMALL_SAMPLE} events", (ROOT / "docs" / "base-rates.md").read_text())


if __name__ == "__main__":
    unittest.main()
