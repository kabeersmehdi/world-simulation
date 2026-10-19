"""Hebrew and English news headlines from RSS feeds."""

from ..signals import indicators_for, topics_for
from ..store import make_observation
from .text import parse_rss_date, rss_items, strip_html

NEWS_INDICATORS = {"airspace", "home_front", "reserves", "late_night_cabinet"}


def collect(source, xml, observed_at, root):
    out = []
    for item in rss_items(xml):
        if not item["link"].startswith("http"):
            continue
        published = parse_rss_date(item["pub_date"])
        excerpt = strip_html(item["description"])
        text = f"{item['title']} {excerpt}"
        out.append(make_observation(
            collector="rss", source_id=source["id"], key=item["guid"] or item["link"],
            observed_at=observed_at, published_at=published, title=item["title"],
            excerpt=excerpt, url=item["link"], lang=source["lang"],
            indicators=indicators_for(text, published, NEWS_INDICATORS),
            tags=topics_for(text), root=root,
        ))
    return out
