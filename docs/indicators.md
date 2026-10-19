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
| `gps_jamming` | Civil aircraft over Israel and the Levant, or the Gulf and Hormuz, reporting degraded GPS accuracy | gpsjam | 24 |
| `infrastructure_fire` | NASA satellites detect a fire at a named refinery, oil terminal, port or nuclear site | firms | 48 |

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

## GPS jamming
Every ADS-B position report carries NACp, the aircraft's own estimate of its GPS error. Healthy receivers report 8 to 11 (error under 93 m). Jamming or spoofing drops it, usually to 0. The collector reads two areas from adsb.lol: Israel and the Levant (200 nautical miles around 32.5 N, 35.0 E) and the Gulf and Hormuz (250 nautical miles around 26.5 N, 54.0 E).

| Setting | Value |
|---|---|
| Degraded below NACp | 8 |
| Minimum aircraft reporting | 10 |
| Minimum degraded aircraft | 5 |
| Minimum degraded share | 20% |

`gps_jamming` fires when all four are met in one area at once. On 10/19/2026 the Levant showed 0 of 31 degraded and the Gulf 5 of 102 (5%), so the bar sits well above the quiet level. Israel has jammed GPS on and off since October 2023, so a long run of hits is a standing condition, not a new signal. Raise the share if it fires every day. Few aircraft at night means few readings, which is why there is a minimum count.

## Satellite fire detections (NASA FIRMS)
VIIRS instruments on three satellites (S-NPP, NOAA-20, NOAA-21) detect heat at 375 m resolution several times a day, and NASA publishes the detections within about three hours. The collector reads the last 24 hours around each site below. It needs a free key from NASA in `FIRMS_MAP_KEY`; without one it is skipped. Low-confidence pixels are ignored.

Refineries and oil processing plants flare gas every day, so they only count when the heat is far above a flare. Nuclear sites, ports and storage terminals do not flare, so two solid detections there are enough.

| Site kind | Minimum solid detections | Minimum total fire power (MW) |
|---|---|---|
| flare | 6 | 100 |
| no_flare | 2 | 0 |

| Site | Name | Lat, lon | Radius (km) | Kind |
|---|---|---|---|---|
| abadan-refinery | Abadan refinery | 30.349, 48.28 | 4 | flare |
| bandar-abbas-refineries | Bandar Abbas refineries | 27.165, 56.06 | 5 | flare |
| isfahan-refinery | Isfahan refinery | 32.784, 51.507 | 4 | flare |
| tehran-refinery | Tehran refinery | 35.54, 51.424 | 4 | flare |
| kharg-island | Kharg Island oil terminal | 29.241, 50.312 | 5 | flare |
| bushehr-npp | Bushehr nuclear power plant | 28.829, 50.884 | 3 | no_flare |
| natanz | Natanz enrichment site | 33.725, 51.724 | 3 | no_flare |
| fordow | Fordow enrichment site | 34.884, 50.997 | 3 | no_flare |
| abqaiq | Abqaiq oil processing (Saudi Arabia) | 25.936, 49.668 | 6 | flare |
| ras-tanura | Ras Tanura refinery and terminal (Saudi Arabia) | 26.693, 50.096 | 5 | flare |
| fujairah-terminal | Fujairah oil terminal (UAE) | 25.199, 56.354 | 5 | no_flare |
| haifa-bazan | Bazan refinery, Haifa | 32.792, 35.055 | 3 | flare |
| ashdod-refinery | Ashdod refinery | 31.842, 34.681 | 3 | flare |
| hodeidah-port | Hodeidah port | 14.837, 42.936 | 4 | no_flare |

Coordinates come from OpenStreetMap and were checked on 10/19/2026. The thresholds are a starting guess: watch a week of readings (every site with any heat is saved, even when nothing fires) and raise the flare bar if a refinery fires on a normal day. Satellite passes are hours apart and clouds or smoke can hide a fire, so a quiet reading proves nothing.

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
