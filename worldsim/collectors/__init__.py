"""Run every configured collector. One failing feed never stops the others."""

import json
import os
from datetime import datetime, timezone
from pathlib import Path

from .. import ROOT
from . import adsb, advisory, firms, fleet, gpsjam, rss, telegram
from .http import NotConfigured, fetch_text

PARSERS = {"rss": rss.collect, "telegram": telegram.collect, "adsb": adsb.collect,
           "fleet": fleet.collect, "advisory": advisory.collect,
           "gpsjam": gpsjam.collect, "firms": firms.collect}

# Kinds that build their own requests (keys, several calls). They get fetch and the environment.
FETCHERS = {"firms": firms.fetch}


def load_sources(root=ROOT):
    return json.loads((Path(root) / "config" / "sources.json").read_text(encoding="utf-8"))


def run(root=ROOT, fetch=fetch_text, now=None, only=None, env=None):
    """Return (observations, report). report has one line per source.

    A source whose key is missing is reported as skipped, not failed.
    """
    env = os.environ if env is None else env
    observed_at = (now or datetime.now(timezone.utc)).replace(microsecond=0).isoformat()
    observations, report = [], []
    for source in load_sources(root)["sources"]:
        if only and source["id"] not in only:
            continue
        try:
            kind = source["kind"]
            raw = FETCHERS[kind](source, fetch, env) if kind in FETCHERS else fetch(source["url"])
            items = PARSERS[kind](source, raw, observed_at, root)
            observations.extend(items)
            flagged = sum(1 for i in items if i["indicators"])
            report.append({"source": source["id"], "ok": True, "items": len(items), "flagged": flagged})
        except NotConfigured as exc:
            report.append({"source": source["id"], "ok": True, "skipped": f"not configured ({exc})"})
        except Exception as exc:  # noqa: BLE001 - report every failure, keep going
            report.append({"source": source["id"], "ok": False, "error": f"{type(exc).__name__}: {exc}"})
    return observations, report
