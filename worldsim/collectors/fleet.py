"""Carrier strike groups near Israel and Iran, from the weekly USNI News fleet tracker."""

import re

from ..store import make_observation
from .text import parse_rss_date, rss_items, strip_html

REGIONS = ["Eastern Mediterranean", "Mediterranean", "Red Sea", "Arabian Sea", "Gulf of Oman",
           "Persian Gulf", "Arabian Gulf", "Gulf of Aden", "Middle East"]
# The tracker groups ships under headings such as "In the Red Sea" on their own line.
_HEADING = re.compile(r"(?:^|\n)\s*In the ([A-Z][A-Za-z ]+?)\s*(?=\n)")
_CARRIER = re.compile(r"USS ([A-Z][A-Za-z. ]+?) \(CVN-(\d+)\)")


def carriers_in_region(body):
    """Return [(carrier, region)] for carriers listed under a heading near Israel or Iran."""
    text = strip_html(body)
    heads = list(_HEADING.finditer(text))
    found = []
    for i, head in enumerate(heads):
        region = next((r for r in REGIONS if r in head.group(1)), None)
        if not region:
            continue
        end = heads[i + 1].start() if i + 1 < len(heads) else len(text)
        for name, hull in _CARRIER.findall(text[head.end():end]):
            pair = (f"USS {' '.join(name.split())} (CVN-{hull})", region)
            if pair not in found:
                found.append(pair)
    return found


def collect(source, xml, observed_at, root):
    out = []
    for item in rss_items(xml)[:3]:
        pairs = carriers_in_region(item["content"] or item["description"])
        if not pairs:
            continue
        summary = "; ".join(f"{c} in {r}" for c, r in pairs)
        out.append(make_observation(
            collector="fleet", source_id=source["id"], key=item["guid"] or item["link"],
            observed_at=observed_at, published_at=parse_rss_date(item["pub_date"]),
            title=f"{item['title']}: {summary}", excerpt=summary, url=item["link"], lang="en",
            indicators=["us_military_moves"], tags=["carrier"],
            data={"carriers": [{"carrier": c, "region": r} for c, r in pairs]}, root=root,
        ))
    return out
