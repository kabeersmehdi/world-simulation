"""US military aircraft in the region, from the adsb.lol military feed.

Class codes and the region box are mirrored in docs/indicators.md.
Many military flights switch transponders off, so absence proves nothing.
"""

import json

from ..store import make_observation

REGION = {"lat_min": 10.0, "lat_max": 42.0, "lon_min": 24.0, "lon_max": 64.0}
AIRCRAFT_CLASSES = {
    "tanker": ["K35R", "K35E", "KC10", "KC46"],
    "bomber": ["B52", "B1", "B2"],
    "surveillance": ["R135", "E3TF", "E3CF", "E6", "P8", "Q4"],
}
MIN_AIRCRAFT_FOR_INDICATOR = 3

_CODE_TO_CLASS = {code: cls for cls, codes in AIRCRAFT_CLASSES.items() for code in codes}


def in_region(ac):
    lat, lon = ac.get("lat"), ac.get("lon")
    if lat is None or lon is None:
        return False
    return REGION["lat_min"] <= lat <= REGION["lat_max"] and REGION["lon_min"] <= lon <= REGION["lon_max"]


def classify(ac):
    return _CODE_TO_CLASS.get((ac.get("t") or "").upper())


def collect(source, text, observed_at, root):
    feed = json.loads(text)
    spotted = []
    for ac in feed.get("ac", []):
        cls = classify(ac)
        if cls and in_region(ac):
            spotted.append({"hex": ac.get("hex"), "type": ac.get("t"), "class": cls,
                            "callsign": (ac.get("flight") or "").strip(), "lat": ac.get("lat"), "lon": ac.get("lon")})
    if not spotted:
        return []
    counts = {cls: sum(1 for s in spotted if s["class"] == cls) for cls in AIRCRAFT_CLASSES}
    summary = ", ".join(f"{n} {cls}" for cls, n in counts.items() if n)
    hour_key = observed_at[:13]  # one snapshot record per hour
    return [make_observation(
        collector="adsb", source_id=source["id"], key=hour_key, observed_at=observed_at,
        published_at=observed_at, title=f"Military aircraft in region: {summary}",
        url="https://adsb.lol/?mil", lang="data",
        indicators=["us_military_moves"] if len(spotted) >= MIN_AIRCRAFT_FOR_INDICATOR else [],
        tags=["aircraft"], data={"counts": counts, "aircraft": spotted[:40]}, root=root,
    )]
