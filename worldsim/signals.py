"""Tag observations with leading indicators and topics.

The keyword lists are mirrored in docs/indicators.md and locked by
tests/test_knowledge_lock.py. Change both together.
"""

from datetime import datetime
from zoneinfo import ZoneInfo

ISRAEL_TZ = ZoneInfo("Asia/Jerusalem")

# Indicator -> keywords. Plain substring match, case-insensitive for Latin text,
# so Hebrew prefixes attached to a word still match.
INDICATOR_KEYWORDS = {
    "airspace": [
        "המרחב האווירי ייסגר",
        "המרחב האווירי נסגר",
        "סגירת המרחב האווירי",
        "סגירת השמיים",
        "airspace closed",
        "airspace closure",
        "closes airspace",
        "NOTAM",
    ],
    "home_front": ["פיקוד העורף", "Home Front Command"],
    "reserves": ["צו 8", "גיוס מילואים", "גיוס נרחב", "call-up of reservists", "reservists called up"],
    "late_night_cabinet": ["קבינט", "security cabinet"],
    "us_advisory": ["ordered departure", "authorized departure", "ordered the departure", "authorized the departure"],
}

# Cabinet mentions only count when reported between these Israel-time hours.
LATE_NIGHT_START_HOUR = 21
LATE_NIGHT_END_HOUR = 5

TOPIC_KEYWORDS = {
    "iran": ["איראן", "טהרן", "Iran", "Tehran"],
    "hezbollah": ["חיזבאללה", "Hezbollah"],
    "houthis": ["חות'ים", "חותים", "Houthi"],
    "gaza": ["עזה", "חמאס", "Gaza", "Hamas"],
    "united-states": ['ארה"ב', "טראמפ", "וושינגטון", "Trump", "Washington", "Pentagon"],
    "election": ["בחירות", "סקר", "election", "poll"],
    "coalition": ["קואליציה", "coalition"],
}


def _contains(text, keyword):
    if keyword.isascii():
        return keyword.lower() in text.lower()
    return keyword in text


def is_late_night(published_at):
    """True if a timestamp falls in the late-night window, Israel time."""
    if not published_at:
        return False
    if isinstance(published_at, str):
        published_at = datetime.fromisoformat(published_at.replace("Z", "+00:00"))
    hour = published_at.astimezone(ISRAEL_TZ).hour
    return hour >= LATE_NIGHT_START_HOUR or hour < LATE_NIGHT_END_HOUR


def indicators_for(text, published_at=None, allowed=None):
    """Return the sorted indicators a piece of text triggers.

    allowed limits which indicators this collector may raise (an advisory
    feed should not raise 'home_front' because it mentions Israel).
    """
    found = set()
    for indicator, words in INDICATOR_KEYWORDS.items():
        if allowed is not None and indicator not in allowed:
            continue
        if any(_contains(text, w) for w in words):
            found.add(indicator)
    if "late_night_cabinet" in found and not is_late_night(published_at):
        found.discard("late_night_cabinet")
    return sorted(found)


def topics_for(text):
    return sorted(t for t, words in TOPIC_KEYWORDS.items() if any(_contains(text, w) for w in words))
