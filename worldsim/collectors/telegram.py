"""Public Telegram channels, read from the t.me/s/<channel> web preview (no login, no keys)."""

import re

from ..signals import indicators_for, topics_for
from ..store import make_observation
from .rss import NEWS_INDICATORS
from .text import strip_html

_MESSAGE = re.compile(r'<div class="tgme_widget_message [^"]*"[^>]*data-post="([^"]+)"(.*?)(?=<div class="tgme_widget_message [^"]*"[^>]*data-post=|\Z)', re.S)
_TEXT = re.compile(r'<div class="tgme_widget_message_text[^"]*"[^>]*>(.*?)</div>', re.S)
_TIME = re.compile(r'<time[^>]*datetime="([^"]+)"')


def parse(html_text):
    posts = []
    for post_id, body in _MESSAGE.findall(html_text):
        text_m = _TEXT.search(body)
        time_m = _TIME.search(body)
        text = strip_html(text_m.group(1)) if text_m else ""
        if not text:
            continue
        posts.append({"post": post_id, "text": text, "published_at": time_m.group(1) if time_m else None})
    return posts


def collect(source, html_text, observed_at, root):
    out = []
    for post in parse(html_text):
        first_line = post["text"].split("\n", 1)[0]
        out.append(make_observation(
            collector="telegram", source_id=source["id"], key=post["post"],
            observed_at=observed_at, published_at=post["published_at"],
            title=first_line[:160], excerpt=post["text"], url=f"https://t.me/{post['post']}",
            lang=source["lang"],
            indicators=indicators_for(post["text"], post["published_at"], NEWS_INDICATORS),
            tags=topics_for(post["text"]) + ["unverified"], root=root,
        ))
    return out
