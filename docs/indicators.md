---
type: rubric
title: Leading indicators
status: active
generated:
  by: human-reviewed
  at: 2026-10-18
stale_after: 2027-01-18
---

# Leading indicators

Big operations usually leave public tracks a day or two ahead. No single signal means much. When several different kinds line up inside their windows, the odds move. The watch level is a heuristic, **not calibrated**, until enough past events are logged against it.

The tables below are locked to `worldsim/signals.py` and `worldsim/watch.py` by a test. Change both together.

## Indicators

| Indicator | What it is | Collector | Window (hours) |
|---|---|---|---|
| `airspace` | Airspace closures or notices to pilots over Israel and nearby | rss, telegram | 48 |
| `home_front` | Home Front Command instructions (schools, gatherings) | rss, telegram | 48 |
| `reserves` | Reserve call-ups, including emergency "Tzav 8" orders | rss, telegram | 48 |
| `late_night_cabinet` | Security cabinet meetings reported between 21:00 and 05:00 Israel time | rss, telegram | 48 |
| `us_advisory` | State Department advisory updates mentioning ordered or authorized departure | advisory | 72 |
| `us_military_moves` | US tankers, bombers or surveillance aircraft in the region, or a carrier strike group reported nearby | adsb, fleet | 192 |

The fleet tracker is weekly, which is why `us_military_moves` has an eight-day window.

## Keywords
Matching is a plain substring check, so Hebrew prefixes (ה, ו, ב, ל, ש) still match.

| Indicator | Keyword |
|---|---|
| airspace | המרחב האווירי ייסגר |
| airspace | המרחב האווירי נסגר |
| airspace | סגירת המרחב האווירי |
| airspace | סגירת השמיים |
| airspace | airspace closed |
| airspace | airspace closure |
| airspace | closes airspace |
| airspace | NOTAM |
| home_front | פיקוד העורף |
| home_front | Home Front Command |
| reserves | צו 8 |
| reserves | גיוס מילואים |
| reserves | גיוס נרחב |
| reserves | call-up of reservists |
| reserves | reservists called up |
| late_night_cabinet | קבינט |
| late_night_cabinet | security cabinet |
| us_advisory | ordered departure |
| us_advisory | authorized departure |
| us_advisory | ordered the departure |
| us_advisory | authorized the departure |

## Aircraft classes counted
ICAO type codes from the adsb.lol military feed, inside latitude 10 to 42 and longitude 24 to 64 (eastern Mediterranean to the Gulf).

| Class | Type codes |
|---|---|
| tanker | K35R, K35E, KC10, KC46 |
| bomber | B52, B1, B2 |
| surveillance | R135, E3TF, E3CF, E6, P8, Q4 |

Some databases list the KC-46 under its airliner base code (B762), which also covers civilian jets, so it is not counted.

`us_military_moves` fires when at least 3 of these are in the box at once. Many military flights switch transponders off, so a quiet sky proves nothing.

## Watch level

| Distinct indicators active | Level |
|---|---|
| 0 to 1 | baseline |
| 2 | elevated |
| 3 or more | high |

## Known gaps
- Home Front Command's own alert feed blocks requests from outside Israel. Its instructions are picked up from news instead.
- The US Embassy Israel alerts page blocks automated requests. The State Department advisory feed is used instead.
- There is no keyless public notice-to-pilots feed. Airspace closures are picked up from news.
