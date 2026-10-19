"""Run every configured collector. One failing feed never stops the others."""

import json
from datetime import datetime, timezone
from pathlib import Path

from .. import ROOT
from . import adsb, advisory, fleet, rss, telegram
from .http import fetch_text

PARSERS = {"rss": rss.collect, "telegram": telegram.collect, "adsb": adsb.collect,
           "fleet": fleet.collect, "advisory": advisory.collect}


def load_sources(root=ROOT):
    return json.loads((Path(root) / "config" / "sources.json").read_text(encoding="utf-8"))


def run(root=ROOT, fetch=fetch_text, now=None, only=None):
    """Return (observations, report). report has one line per source."""
    observed_at = (now or datetime.now(timezone.utc)).replace(microsecond=0).isoformat()
    observations, report = [], []
    for source in load_sources(root)["sources"]:
        if only and source["id"] not in only:
            continue
        try:
            items = PARSERS[source["kind"]](source, fetch(source["url"]), observed_at, root)
            observations.extend(items)
            flagged = sum(1 for i in items if i["indicators"])
            report.append({"source": source["id"], "ok": True, "items": len(items), "flagged": flagged})
        except Exception as exc:  # noqa: BLE001 - report every failure, keep going
            report.append({"source": source["id"], "ok": False, "error": f"{type(exc).__name__}: {exc}"})
    return observations, report
