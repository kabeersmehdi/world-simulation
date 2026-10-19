"""GPS jamming: how many civil aircraft in an area report degraded GPS accuracy.

Every ADS-B position carries NACp, the aircraft's own estimate of its GPS error.
Healthy receivers report 8 to 11 (error under 93 m). Jamming or spoofing drops it,
usually to 0. A sudden share of degraded aircraft over an area is a sign that air
defenses or electronic warfare units are active. Thresholds are mirrored in
docs/indicators.md and locked by a test. Heuristic, not calibrated.
"""

import json

from ..store import make_observation

DEGRADED_BELOW_NACP = 8      # NACp 0-7 counts as degraded
MIN_REPORTING = 10           # too few aircraft in the sky says nothing
MIN_DEGRADED = 5
MIN_DEGRADED_SHARE = 0.20


def count(feed):
    reporting = [ac for ac in feed.get("ac", []) if isinstance(ac.get("nac_p"), int)]
    degraded = [ac for ac in reporting if ac["nac_p"] < DEGRADED_BELOW_NACP]
    return reporting, degraded


def fires(n_reporting, n_degraded):
    return (n_reporting >= MIN_REPORTING and n_degraded >= MIN_DEGRADED
            and n_degraded / n_reporting >= MIN_DEGRADED_SHARE)


def collect(source, text, observed_at, root):
    reporting, degraded = count(json.loads(text))
    if not reporting:
        return []
    share = len(degraded) / len(reporting)
    hour_key = observed_at[:13]  # one snapshot record per hour
    return [make_observation(
        collector="gpsjam", source_id=source["id"], key=hour_key, observed_at=observed_at,
        published_at=observed_at,
        title=f"GPS degraded over {source['area']}: {len(degraded)} of {len(reporting)} aircraft ({share:.0%})",
        url=source["map_url"], lang="data",
        indicators=["gps_jamming"] if fires(len(reporting), len(degraded)) else [],
        tags=["aircraft", "gps"],
        data={"reporting": len(reporting), "degraded": len(degraded), "share": round(share, 3),
              "degraded_aircraft": [{"hex": ac.get("hex"), "callsign": (ac.get("flight") or "").strip(),
                                     "nac_p": ac["nac_p"], "lat": ac.get("lat"), "lon": ac.get("lon")}
                                    for ac in degraded[:40]]},
        root=root,
    )]
