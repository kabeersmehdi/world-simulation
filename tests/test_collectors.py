"""Collectors against saved fixtures. No network."""

import json
import unittest

from worldsim import collectors
from worldsim.collectors import adsb, advisory, firms, fleet, gpsjam, rss, telegram
from worldsim.collectors.http import NotConfigured
from worldsim.collectors.text import parse_rss_date, rss_items

from .helpers import NOW, NOW_ISO, fixture, isolated_root

SRC = {"id": "test-src", "lang": "he"}


class RssTests(unittest.TestCase):
    def test_parses_cdata_and_tags_indicators(self):
        obs = rss.collect(SRC, fixture("ynet.xml"), NOW_ISO, isolated_root())
        by_url = {o["url"].rsplit("/", 1)[1]: o for o in obs}
        self.assertEqual(len(obs), 4)
        self.assertEqual(by_url["aaa111"]["indicators"], ["home_front"])
        self.assertEqual(by_url["bbb222"]["indicators"], ["late_night_cabinet"])
        self.assertEqual(by_url["ccc333"]["indicators"], [])
        self.assertIn("iran", by_url["bbb222"]["tags"])
        self.assertIn("election", by_url["ddd444"]["tags"])

    def test_dates_to_utc(self):
        self.assertEqual(parse_rss_date("Mon, 19 Oct 2026 05:20:11 +0300"), "2026-10-19T02:20:11+00:00")
        self.assertEqual(parse_rss_date("Wed, 26 Aug 2026"), "2026-08-26T00:00:00+00:00")
        self.assertIsNone(parse_rss_date("not a date"))

    def test_survives_malformed_xml(self):
        self.assertEqual(len(rss_items("<rss><item><title>a & b</title><link>https://x.org/1</link></item><item>")), 1)

    def test_excerpt_is_short(self):
        long_feed = fixture("ynet.xml").replace("הנחיות חדשות לתושבי הצפון", "מילה " * 400)
        obs = rss.collect(SRC, long_feed, NOW_ISO, isolated_root())
        self.assertTrue(all(len(o["excerpt"]) <= 200 for o in obs))


class TelegramTests(unittest.TestCase):
    def test_parses_posts(self):
        obs = telegram.collect({"id": "tg-kann", "lang": "he"}, fixture("telegram.html"), NOW_ISO, isolated_root())
        self.assertEqual(len(obs), 2)
        self.assertEqual(obs[0]["url"], "https://t.me/kann_news/5001")
        self.assertIn("reserves", obs[0]["indicators"])
        self.assertIn("unverified", obs[0]["tags"])
        self.assertEqual(obs[0]["title"], "צו 8 נשלח לאלפי מילואימניקים")


GPS_SRC = {"id": "gpsjam-levant", "area": "Israel and the Levant", "map_url": "https://gpsjam.org/"}


class GpsJamTests(unittest.TestCase):
    def test_counts_degraded_and_fires(self):
        obs = gpsjam.collect(GPS_SRC, fixture("gpsjam.json"), NOW_ISO, isolated_root())
        self.assertEqual(len(obs), 1)
        self.assertEqual(obs[0]["collector"], "gpsjam")
        self.assertEqual(obs[0]["data"]["reporting"], 18)  # the aircraft with no NACp is skipped
        self.assertEqual(obs[0]["data"]["degraded"], 6)
        self.assertEqual(obs[0]["indicators"], ["gps_jamming"])
        self.assertIn("6 of 18", obs[0]["title"])

    def test_quiet_sky_does_not_fire(self):
        feed = json.loads(fixture("gpsjam.json"))
        for ac in feed["ac"]:
            if "nac_p" in ac:
                ac["nac_p"] = 9
        obs = gpsjam.collect(GPS_SRC, json.dumps(feed), NOW_ISO, isolated_root())
        self.assertEqual(obs[0]["indicators"], [])

    def test_thresholds(self):
        self.assertFalse(gpsjam.fires(9, 9))     # too few aircraft to judge
        self.assertFalse(gpsjam.fires(100, 4))   # too few degraded
        self.assertFalse(gpsjam.fires(100, 19))  # under 20%
        self.assertTrue(gpsjam.fires(100, 20))

    def test_nacp_8_is_healthy(self):
        _, degraded = gpsjam.count({"ac": [{"nac_p": 8}, {"nac_p": 7}, {"nac_p": None}]})
        self.assertEqual([a["nac_p"] for a in degraded], [7])

    def test_empty_sky_gives_nothing(self):
        self.assertEqual(gpsjam.collect(GPS_SRC, '{"ac": []}', NOW_ISO, isolated_root()), [])


class AdsbTests(unittest.TestCase):
    def test_counts_only_listed_classes_in_region(self):
        obs = adsb.collect({"id": "adsb"}, fixture("adsb.json"), NOW_ISO, isolated_root())
        self.assertEqual(len(obs), 1)
        self.assertEqual(obs[0]["data"]["counts"], {"tanker": 2, "bomber": 0, "surveillance": 1})
        self.assertEqual(obs[0]["indicators"], ["us_military_moves"])

    def test_below_threshold_does_not_fire(self):
        feed = json.loads(fixture("adsb.json"))
        feed["ac"] = feed["ac"][:1]
        obs = adsb.collect({"id": "adsb"}, json.dumps(feed), NOW_ISO, isolated_root())
        self.assertEqual(obs[0]["indicators"], [])

    def test_empty_sky_gives_nothing(self):
        self.assertEqual(adsb.collect({"id": "adsb"}, '{"ac": []}', NOW_ISO, isolated_root()), [])


class FleetTests(unittest.TestCase):
    def test_finds_carriers_under_regional_headings(self):
        obs = fleet.collect({"id": "usni"}, fixture("usni.xml"), NOW_ISO, isolated_root())
        carriers = obs[0]["data"]["carriers"]
        self.assertIn({"carrier": "USS Gerald R. Ford (CVN-78)", "region": "Eastern Mediterranean"}, carriers)
        self.assertIn({"carrier": "USS George Washington (CVN-73)", "region": "Arabian Sea"}, carriers)
        self.assertNotIn("Abraham Lincoln", json.dumps(carriers))


class AdvisoryTests(unittest.TestCase):
    def test_regional_only_and_departure_flag(self):
        obs = advisory.collect({"id": "state"}, fixture("advisories.xml"), NOW_ISO, isolated_root())
        countries = [o["data"]["country"] for o in obs]
        self.assertEqual(countries, ["Israel", "Lebanon"])
        self.assertEqual(obs[0]["indicators"], ["us_advisory"])
        self.assertEqual(obs[0]["data"]["level"], 3)
        self.assertEqual(obs[1]["indicators"], [])


def firms_source(root):
    return next(s for s in collectors.load_sources(root)["sources"] if s["id"] == "firms-iran-gulf")


class FirmsTests(unittest.TestCase):
    def test_site_rules(self):
        root = isolated_root()
        src = firms_source(root)
        src["sites"] += [s for s in collectors.load_sources(root)["sources"] if s["id"] == "firms-israel"][0]["sites"]
        obs = {o["data"]["site"]: o for o in firms.collect(src, fixture("firms.csv"), NOW_ISO, root)}
        self.assertEqual(set(obs), {"abadan-refinery", "haifa-bazan", "bushehr-npp", "natanz"})  # farmland point dropped
        self.assertEqual(obs["abadan-refinery"]["indicators"], ["infrastructure_fire"])
        self.assertEqual(obs["abadan-refinery"]["data"]["solid"], 12)  # low-confidence and old pixels ignored
        self.assertEqual(obs["abadan-refinery"]["data"]["frp_mw"], 300.0)
        self.assertEqual(obs["abadan-refinery"]["published_at"], "2026-10-18T20:21:00+00:00")
        self.assertEqual(obs["haifa-bazan"]["indicators"], [])   # a normal flare
        self.assertEqual(obs["bushehr-npp"]["indicators"], [])   # one pixel is not enough
        self.assertEqual(obs["natanz"]["indicators"], ["infrastructure_fire"])

    def test_unreadable_rows_fail_loudly(self):
        with self.assertRaises(ValueError):
            firms.parse("latitude,longitude,acq_date\nx,y,z\n")

    def test_asks_for_two_days(self):
        urls = []
        firms.fetch({"bbox": [1, 2, 3, 4]}, lambda url: urls.append(url) or "latitude\n",
                    env={"FIRMS_MAP_KEY": "0123456789abcdef0123456789abcdef"})
        self.assertTrue(all(u.endswith("/1,2,3,4/2") for u in urls))

    def test_skipped_without_key(self):
        with self.assertRaises(NotConfigured):
            firms.fetch({"bbox": [1, 2, 3, 4]}, lambda url: "", env={})

    def test_fetch_joins_satellites_and_hides_key(self):
        urls = []

        def fake(url):
            urls.append(url)
            return fixture("firms.csv")
        text = firms.fetch({"bbox": [47, 24, 58, 36]}, fake, env={"FIRMS_MAP_KEY": "SECRET"})
        self.assertEqual(len(urls), 3)
        self.assertIn("/SECRET/VIIRS_NOAA20_NRT/47,24,58,36/2", urls[1])
        self.assertEqual(text.count("latitude,"), 1)
        self.assertEqual(len(firms.parse(text)), 3 * len(firms.parse(fixture("firms.csv"))))

        def broken(url):
            raise OSError(f"failed {url}")
        with self.assertRaises(RuntimeError) as ctx:
            firms.fetch({"bbox": [1, 2, 3, 4]}, broken, env={"FIRMS_MAP_KEY": "SECRET"})
        self.assertNotIn("SECRET", str(ctx.exception))
        with self.assertRaises(RuntimeError) as ctx:
            firms.fetch({"bbox": [1, 2, 3, 4]}, lambda url: "Invalid MAP_KEY SECRET", env={"FIRMS_MAP_KEY": "SECRET"})
        self.assertNotIn("SECRET", str(ctx.exception))

    def test_runner_reports_skipped(self):
        _, report = collectors.run(isolated_root(), fetch=lambda url: "", now=NOW, only={"firms-israel"}, env={})
        self.assertEqual(report, [{"source": "firms-israel", "ok": True, "skipped": "not configured (FIRMS_MAP_KEY not set)"}])


class FallbackTests(unittest.TestCase):
    def test_blocked_feed_falls_back_to_google_news(self):
        def fake(url):
            if "timesofisrael.com/feed" in url:
                raise OSError("HTTP Error 403: Forbidden")
            return fixture("google_news_toi.xml")
        obs, report = collectors.run(isolated_root(), fetch=fake, now=NOW, only={"times-of-israel"}, env={})
        self.assertTrue(report[0]["ok"])
        self.assertIn("403", report[0]["via"])
        self.assertEqual(len(obs), 3)
        self.assertEqual(obs[0]["title"], "Headline 0 about Iran")  # suffix stripped
        self.assertIn("iran", obs[0]["tags"])

    def test_direct_feed_used_when_it_works(self):
        urls = []

        def fake(url):
            urls.append(url)
            return fixture("ynet.xml")
        _, report = collectors.run(isolated_root(), fetch=fake, now=NOW, only={"times-of-israel"}, env={})
        self.assertNotIn("via", report[0])
        self.assertEqual(len(urls), 1)

    def test_no_fallback_still_fails(self):
        def fake(url):
            raise OSError("HTTP Error 403: Forbidden")
        _, report = collectors.run(isolated_root(), fetch=fake, now=NOW, only={"ynet"}, env={})
        self.assertFalse(report[0]["ok"])


class RunnerTests(unittest.TestCase):
    def test_one_failing_feed_does_not_stop_the_rest(self):
        def fake_fetch(url):
            if "ynet" in url:
                return fixture("ynet.xml")
            raise OSError("network off in tests")
        obs, report = collectors.run(isolated_root(), fetch=fake_fetch, now=NOW, env={"FIRMS_MAP_KEY": "0123456789abcdef0123456789abcdef"})
        ok = [r for r in report if r["ok"]]
        self.assertEqual([r["source"] for r in ok], ["ynet"])
        self.assertTrue(all("network off" in r["error"] for r in report if not r["ok"]))
        self.assertEqual(len(obs), 4)


if __name__ == "__main__":
    unittest.main()
