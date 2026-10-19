"""NASA FIRMS satellite fire detections at named energy and nuclear sites.

VIIRS on three satellites spots heat at 375 m resolution several times a day.
Refineries flare gas every day, so a refinery only counts once the heat is far
above a flare. Nuclear sites, ports and storage terminals do not flare, so a
couple of solid detections there is enough. Sites and thresholds are mirrored in
docs/indicators.md and locked by a test. Heuristic, not calibrated.

Needs a free FIRMS key in FIRMS_MAP_KEY. Without it the source is skipped.
"""

import csv
import io
import math
import os
from datetime import datetime, timedelta, timezone

from ..store import make_observation
from .http import NotConfigured

KEY_VAR = "FIRMS_MAP_KEY"
# DAY_RANGE 1 means "today, UTC" only, which is nearly empty early in the UTC day.
# Ask for two days and keep the last 24 hours ourselves.
API = "https://firms.modaps.eosdis.nasa.gov/api/area/csv/{key}/{sat}/{bbox}/2"
LOOKBACK_HOURS = 24
SATELLITES = ["VIIRS_SNPP_NRT", "VIIRS_NOAA20_NRT", "VIIRS_NOAA21_NRT"]

# site kind -> (minimum solid detections, minimum total fire radiative power in MW)
# On 10/18/2026 one satellite alone saw 7 to 10 flare pixels and 15 to 38 MW at the
# busiest refineries, so three satellites see about three times that on a normal day.
RULES = {"flare": (10, 300.0), "no_flare": (2, 0.0)}
SOLID_CONFIDENCE = {"n", "h", "nominal", "high"}  # VIIRS low-confidence pixels are ignored


def fetch(source, fetch_text, env=None):
    """Raw CSV from all three VIIRS satellites for the source's box, last 24 hours."""
    env = os.environ if env is None else env
    key = env.get(KEY_VAR)
    if not key:
        raise NotConfigured(f"{KEY_VAR} not set")
    bbox = ",".join(str(v) for v in source["bbox"])
    parts = []
    for sat in SATELLITES:
        try:
            text = fetch_text(API.format(key=key, sat=sat, bbox=bbox))
        except Exception as exc:  # never let the key reach a log line
            raise RuntimeError(str(exc).replace(key, "***")) from None
        if not text.startswith("latitude"):
            raise RuntimeError(f"{sat}: not CSV: {text[:80].replace(key, '***')}")
        if parts:  # keep one header row
            text = text.split("\n", 1)[1] if "\n" in text else ""
        parts.append(text)
    return "\n".join(p.strip("\n") for p in parts if p.strip())


def km_between(lat1, lon1, lat2, lon2):
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def parse(csv_text):
    rows = []
    lines = 0
    for row in csv.DictReader(io.StringIO(csv_text)):
        lines += 1
        try:
            t = row["acq_time"].zfill(4)
            at = datetime.strptime(f"{row['acq_date']} {t}", "%Y-%m-%d %H%M").replace(tzinfo=timezone.utc)
            rows.append({"lat": float(row["latitude"]), "lon": float(row["longitude"]),
                         "frp": float(row.get("frp") or 0), "confidence": (row.get("confidence") or "").lower(),
                         "at": at.isoformat(), "satellite": row.get("satellite")})
        except (KeyError, ValueError):
            continue
    if lines and not rows:
        raise ValueError(f"none of {lines} FIRMS rows could be read; the CSV format may have changed")
    return rows


def fires(kind, solid, frp):
    min_count, min_frp = RULES[kind]
    return solid >= min_count and frp >= min_frp


def collect(source, csv_text, observed_at, root):
    cutoff = (datetime.fromisoformat(observed_at) - timedelta(hours=LOOKBACK_HOURS)).isoformat()
    detections = [d for d in parse(csv_text) if d["at"] >= cutoff]
    out = []
    for site in source["sites"]:
        near = [d for d in detections if km_between(site["lat"], site["lon"], d["lat"], d["lon"]) <= site["radius_km"]]
        if not near:
            continue
        solid = [d for d in near if d["confidence"] in SOLID_CONFIDENCE]
        frp = round(sum(d["frp"] for d in solid), 1)
        latest = max(d["at"] for d in near)
        out.append(make_observation(
            collector="firms", source_id=source["id"], key=f"{site['id']}|{observed_at[:13]}",
            observed_at=observed_at, published_at=latest,
            title=f"Satellite heat at {site['name']}: {len(solid)} solid detections, {frp:g} MW",
            url=f"https://firms.modaps.eosdis.nasa.gov/map/#d:24hrs;@{site['lon']},{site['lat']},12z",
            lang="data",
            indicators=["infrastructure_fire"] if fires(site["kind"], len(solid), frp) else [],
            tags=["satellite", "fire", site["kind"]],
            data={"site": site["id"], "kind": site["kind"], "detections": len(near), "solid": len(solid),
                  "frp_mw": frp, "points": near[:40]},
            root=root,
        ))
    return out
