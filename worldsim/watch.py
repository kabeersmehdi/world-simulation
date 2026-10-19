"""Watch level: how many different leading indicators are active right now.

A heuristic, not calibrated. Windows and levels are mirrored in
docs/indicators.md and locked by a test.
"""

from datetime import datetime, timedelta, timezone

from .contracts import parse_datetime

WINDOW_HOURS = {
    "airspace": 48,
    "home_front": 48,
    "reserves": 48,
    "late_night_cabinet": 48,
    "us_advisory": 72,
    "us_military_moves": 192,
    "gps_jamming": 24,
}

# (minimum distinct active indicators, level), checked from the top.
LEVELS = [(3, "high"), (2, "elevated"), (0, "baseline")]


def _when(ob):
    return parse_datetime(ob.get("published_at") or ob["observed_at"])


def level_for(count):
    for minimum, name in LEVELS:
        if count >= minimum:
            return name
    return "baseline"


def watch_status(observations, now=None):
    now = now or datetime.now(timezone.utc)
    indicators = {}
    for name, hours in WINDOW_HOURS.items():
        start = now - timedelta(hours=hours)
        hits = [ob for ob in observations if name in ob["indicators"] and start <= _when(ob) <= now]
        hits.sort(key=_when, reverse=True)
        indicators[name] = {
            "active": bool(hits),
            "window_hours": hours,
            "count": len(hits),
            "latest": [{"title": h["title"], "url": h["url"], "source_id": h["source_id"],
                        "at": h.get("published_at") or h["observed_at"]} for h in hits[:5]],
        }
    active = sum(1 for v in indicators.values() if v["active"])
    return {
        "as_of": now.isoformat(),
        "active_count": active,
        "level": level_for(active),
        "calibrated": False,
        "indicators": indicators,
    }
