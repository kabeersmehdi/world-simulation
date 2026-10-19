"""US State Department travel advisories for Israel and its neighbors."""

import re

from ..signals import indicators_for
from ..store import make_observation
from .text import parse_rss_date, rss_items, strip_html

COUNTRIES = ["Israel", "Iran", "Lebanon", "Syria", "Iraq", "Jordan", "Yemen", "Egypt", "Saudi Arabia",
             "Qatar", "Bahrain", "United Arab Emirates", "Kuwait", "Oman"]
_LEVEL = re.compile(r"Level (\d)")


def collect(source, xml, observed_at, root):
    out = []
    for item in rss_items(xml):
        country = next((c for c in COUNTRIES if item["title"].startswith(c)), None)
        if not country:
            continue
        body = strip_html(item["description"])
        level = _LEVEL.search(item["title"])
        published = parse_rss_date(item["pub_date"])
        out.append(make_observation(
            collector="advisory", source_id=source["id"],
            key=f"{item['link']}|{item['pub_date']}", observed_at=observed_at,
            published_at=published, title=item["title"], excerpt=body, url=item["link"], lang="en",
            indicators=indicators_for(body, published, {"us_advisory"}),
            tags=["advisory", country.lower()],
            data={"country": country, "level": int(level.group(1)) if level else None}, root=root,
        ))
    return out
