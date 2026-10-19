"""Shared parsing helpers: RSS items, HTML stripping, dates."""

import html
import re
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

_TAG = re.compile(r"<[^>]+>")
_CDATA = re.compile(r"<!\[CDATA\[(.*?)\]\]>", re.S)


def strip_html(text):
    text = _CDATA.sub(lambda m: m.group(1), text or "")
    text = re.sub(r"<br\s*/?>", "\n", text, flags=re.I)
    text = html.unescape(_TAG.sub(" ", text))
    return re.sub(r"[ \t\r\f\v]+", " ", text).strip()


def _field(block, name):
    m = re.search(rf"<{name}(?:\s[^>]*)?>(.*?)</{name}\s*>", block, re.S | re.I)
    if not m:
        return ""
    return _CDATA.sub(lambda c: c.group(1), m.group(1)).strip()


def rss_items(xml):
    """Parse RSS 2.0 items with regex, which survives the malformed XML some feeds send."""
    items = []
    for block in re.findall(r"<item\b[^>]*>(.*?)</item\s*>", xml, re.S | re.I):
        items.append({
            "title": strip_html(_field(block, "title")),
            "link": html.unescape(strip_html(_field(block, "link"))),
            "guid": strip_html(_field(block, "guid")),
            "pub_date": _field(block, "pubDate"),
            "description": _field(block, "description"),
            "content": _field(block, "content:encoded"),
        })
    return items


def parse_rss_date(value):
    """RFC 822 date to ISO 8601 UTC. A date with no time is read as midnight UTC."""
    if not value:
        return None
    value = value.strip()
    try:
        dt = parsedate_to_datetime(value)
    except (TypeError, ValueError):
        dt = None
    if dt is None:
        for fmt in ("%a, %d %b %Y", "%d %b %Y"):
            try:
                dt = datetime.strptime(value, fmt)
                break
            except ValueError:
                continue
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).isoformat()
