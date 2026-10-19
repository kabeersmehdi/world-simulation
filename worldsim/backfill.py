"""Rebuild past indicator firings so the lead-lag test has history to work with.

The live log in data/observations only starts when collect first ran. Two
sources can be read backwards for free:

  Telegram   t.me/s/<channel>?before=<post> pages back through a public
             channel. Each post is tagged with the same keyword rules as
             collect, so a backfilled firing means exactly what a live one does.
  Advisories Wayback Machine copies of the State Department advisory feed.
             Each copy lists the newest update per country with its date.

Only the firing itself is kept (post id, time, indicators). No post text is
stored. GPS jamming, NASA fires and airline cancellations have no free history
and are not backfilled.
"""

import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path

from . import ROOT
from .collectors.advisory import COUNTRIES
from .collectors.http import fetch_text
from .collectors.rss import NEWS_INDICATORS
from .collectors.telegram import parse
from .collectors.text import parse_rss_date, rss_items, strip_html
from .contracts import parse_datetime
from .signals import indicators_for

ADVISORY_FEED = "https://travel.state.gov/_res/rss/TAsTWs.xml"
CDX_URL = "https://web.archive.org/cdx/search/cdx?url={url}&from={start}&output=json&filter=statuscode:200&collapse=digest"
SNAPSHOT_URL = "https://web.archive.org/web/{ts}id_/{url}"


def _dir(root):
    return Path(root) / "data" / "backfill"


def load_config(root=ROOT):
    return json.loads((Path(root) / "config" / "leadlag.json").read_text(encoding="utf-8"))


def _fetch_retry(fetch, url, tries=4, pause=0.3):
    for i in range(tries):
        try:
            return fetch(url)
        except Exception:  # noqa: BLE001 - network blips; the last one is raised
            if i == tries - 1:
                raise
            if pause:
                time.sleep(pause * 10 * (i + 1))


def telegram_history(source, since, fetch=fetch_text, max_pages=1500, pause=0.3):
    """Walk a channel back to `since`. Returns (firings, coverage).

    A page that still fails after retries ends the walk early; what was read
    so far is kept and the coverage says how far back it got.
    """
    base = source["url"].split("?")[0]
    url, firings, posts, oldest, newest, prev = base, [], 0, None, None, None
    for _ in range(max_pages):
        try:
            page = parse(_fetch_retry(fetch, url, pause=pause))
        except Exception:  # noqa: BLE001
            break
        if not page:
            break
        first = min(int(p["post"].rsplit("/", 1)[1]) for p in page)
        if prev is not None and first >= prev:
            break  # the page did not move back
        prev = first
        for post in page:
            if not post["published_at"]:
                continue
            at = parse_datetime(post["published_at"])
            if at < since:
                continue
            posts += 1
            oldest = at if oldest is None or at < oldest else oldest
            newest = at if newest is None or at > newest else newest
            found = indicators_for(post["text"], post["published_at"], NEWS_INDICATORS)
            if found:
                firings.append({"source_id": source["id"], "key": post["post"],
                                "at": at.astimezone(timezone.utc).isoformat(), "indicators": found})
        page_oldest = min((parse_datetime(p["published_at"]) for p in page if p["published_at"]), default=None)
        if first <= 1 or (page_oldest and page_oldest < since):
            break
        url = f"{base}?before={first}"
        if pause:
            time.sleep(pause)
    coverage = {"source_id": source["id"], "posts": posts,
                "from": oldest.isoformat() if oldest else None, "to": newest.isoformat() if newest else None}
    return firings, coverage


def advisory_firings(xml, source_id="travel-state-gov"):
    """Advisory updates in one feed copy that mention an ordered or authorized departure."""
    out = []
    for item in rss_items(xml):
        country = next((c for c in COUNTRIES if item["title"].startswith(c)), None)
        published = parse_rss_date(item["pub_date"])
        if not country or not published:
            continue
        found = indicators_for(strip_html(item["description"]), published, {"us_advisory"})
        if found:
            level = re.search(r"Level (\d)", item["title"])
            out.append({"source_id": source_id, "key": f"{country}|{item['pub_date']}", "at": published,
                        "indicators": found, "country": country, "level": int(level.group(1)) if level else None})
    return out


def advisory_history(since, fetch=fetch_text, pause=0.5):
    """One archived copy of the advisory feed per day since `since`. Returns (firings, coverage)."""
    rows = json.loads(fetch(CDX_URL.format(url=ADVISORY_FEED, start=since.strftime("%Y%m%d"))))
    per_day = {}
    for row in rows[1:]:
        per_day.setdefault(row[1][:8], row[1])
    firings, seen = [], set()
    for ts in sorted(per_day.values()):
        try:
            xml = fetch(SNAPSHOT_URL.format(ts=ts, url=ADVISORY_FEED))
        except Exception:  # noqa: BLE001 - one missing copy skips one day only
            continue
        for f in advisory_firings(xml):
            if f["key"] not in seen and parse_datetime(f["at"]) >= since:
                seen.add(f["key"])
                firings.append(f)
        if pause:
            time.sleep(pause)
    days = sorted(per_day)
    coverage = {"source_id": "travel-state-gov", "copies": len(days),
                "from": days[0] if days else None, "to": days[-1] if days else None}
    return firings, coverage


def run(root=ROOT, fetch=fetch_text, pause=0.3, log=print, only=None):
    """Backfill every configured source, or with `only`, just those ids, keeping the rest from the last run."""
    cfg = load_config(root)
    since = datetime.fromisoformat(cfg["since"]).replace(tzinfo=timezone.utc)
    sources = {s["id"]: s for s in json.loads((Path(root) / "config" / "sources.json").read_text(encoding="utf-8"))["sources"]}
    firings, coverage = [], []
    if only:
        firings = [f for f in load(root) if f["source_id"] not in only]
        cov_path = _dir(root) / "coverage.json"
        if cov_path.exists():
            coverage = [c for c in json.loads(cov_path.read_text(encoding="utf-8"))["sources"] if c["source_id"] not in only]
    for sid in cfg["telegram_sources"]:
        if only and sid not in only:
            continue
        try:
            f, c = telegram_history(sources[sid], since, fetch, cfg["max_pages"], pause)
        except Exception as exc:  # noqa: BLE001 - one channel failing skips that channel
            log(f"FAIL {sid}: {type(exc).__name__}: {exc}")
            continue
        log(f"ok   {sid}: {c['posts']} posts since {cfg['since']}, {len(f)} firings")
        firings += f
        coverage.append(c)
    try:
        if only and "travel-state-gov" not in only:
            raise LookupError("skipped")
        f, c = advisory_history(since, fetch, pause)
        log(f"ok   travel-state-gov: {c['copies']} archived copies, {len(f)} departure updates")
        firings += f
        coverage.append(c)
    except LookupError:
        pass
    except Exception as exc:  # noqa: BLE001
        log(f"FAIL travel-state-gov: {type(exc).__name__}: {exc}")
    firings.sort(key=lambda r: r["at"])
    out = _dir(root)
    out.mkdir(parents=True, exist_ok=True)
    (out / "firings.jsonl").write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in firings), encoding="utf-8")
    (out / "coverage.json").write_text(json.dumps({"since": cfg["since"], "sources": coverage}, indent=1) + "\n", encoding="utf-8")
    return firings, coverage


def load(root=ROOT):
    path = _dir(root) / "firings.jsonl"
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
