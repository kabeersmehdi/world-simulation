import json
import unittest

from worldsim import build, store

from .helpers import NOW, isolated_root


class BuildTests(unittest.TestCase):
    def test_build_into_isolated_root(self):
        root = isolated_root()
        at = NOW.isoformat()
        store.save([store.make_observation(collector="rss", source_id="ynet", key="k1", observed_at=at, published_at=at,
                                           title="פיקוד העורף", url="https://www.ynet.co.il/x", lang="he",
                                           indicators=["home_front"], tags=[], root=root)], root)
        data = build.build(root, now=NOW)
        written = json.loads((root / "dashboard" / "data.json").read_text())
        self.assertEqual(written["generated_at"], data["generated_at"])
        self.assertEqual([c["id"] for c in data["countries"]], ["united-states", "israel", "iran"])
        self.assertTrue(all(c["sources"] and isinstance(c["sources"], list) for c in data["countries"]))
        self.assertEqual(data["watch"]["indicators"]["home_front"]["count"], 1)
        self.assertEqual(data["forecasts"]["live"], [])
        self.assertTrue(all(f["illustrative"] for f in data["forecasts"]["demo"]))
        self.assertTrue(data["timeline"][0]["date"] >= data["timeline"][-1]["date"])
        self.assertTrue(data["relationships"])
        seats = next(p for p in data["polls"] if p["measure"] == "knesset_seats")
        self.assertEqual(seats["largest_party_count"]["Yashar"], 5)
        self.assertTrue(all(sum(r["values"].values()) == 120 for r in seats["rows"]))
        self.assertIn("timing", data)

    def test_frontmatter_lists_and_nesting(self):
        root = isolated_root()
        meta, body = build.read_frontmatter(root / "countries" / "israel" / "profile.md")
        self.assertEqual(meta["type"], "country-profile")
        self.assertEqual(meta["generated"]["at"], "2026-10-18")
        self.assertEqual(len(meta["sources"]), 2)
        self.assertTrue(body.startswith("\n# Israel"))


if __name__ == "__main__":
    unittest.main()
