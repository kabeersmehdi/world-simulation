"""Observation storage: one JSON-lines file per UTC day, deduplicated by id."""

import hashlib
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from . import ROOT
from .contracts import parse_datetime, validate

EXCERPT_CHARS = 200  # short excerpt plus link; full articles are never stored


def observation_id(source_id, key):
    return "ob-" + hashlib.sha1(f"{source_id}|{key}".encode()).hexdigest()[:16]


def make_observation(*, collector, source_id, key, observed_at, title, url, lang,
                     indicators, tags, published_at=None, excerpt="", data=None, root=ROOT):
    record = {
        "id": observation_id(source_id, key),
        "collector": collector,
        "source_id": source_id,
        "observed_at": observed_at,
        "published_at": published_at,
        "title": title.strip()[:300] or "(untitled)",
        "excerpt": excerpt.strip()[:EXCERPT_CHARS],
        "url": url,
        "lang": lang,
        "indicators": indicators,
        "tags": tags,
        "data": data,
    }
    return validate(record, "observation", root)


def _obs_dir(root):
    return Path(root) / "data" / "observations"


def save(observations, root=ROOT):
    """Append new observations. Returns how many were new."""
    folder = _obs_dir(root)
    folder.mkdir(parents=True, exist_ok=True)
    by_day = {}
    for ob in observations:
        day = parse_datetime(ob["observed_at"]).astimezone(timezone.utc).date().isoformat()
        by_day.setdefault(day, []).append(ob)
    seen = {ob["id"] for ob in load(root=root, days=None)}
    added = 0
    for day, items in sorted(by_day.items()):
        with open(folder / f"{day}.jsonl", "a", encoding="utf-8") as fh:
            for ob in items:
                if ob["id"] in seen:
                    continue
                seen.add(ob["id"])
                fh.write(json.dumps(ob, ensure_ascii=False) + "\n")
                added += 1
    return added


def load(root=ROOT, days=7, now=None):
    """Load observations from the last `days` days (all of them if days is None)."""
    folder = _obs_dir(root)
    if not folder.exists():
        return []
    files = sorted(folder.glob("*.jsonl"))
    if days is not None:
        now = now or datetime.now(timezone.utc)
        cutoff = (now - timedelta(days=days)).date().isoformat()
        files = [f for f in files if f.stem >= cutoff]
    out = []
    for f in files:
        for line in f.read_text(encoding="utf-8").splitlines():
            if line.strip():
                out.append(json.loads(line))
    return out
