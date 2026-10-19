"""Assemble every stage's output into dashboard/data.json."""

import json
import re
from datetime import datetime, timezone
from pathlib import Path

from . import ROOT, backtest, baserates, eventstudy, forecasts, markets, outlook, polls, scoring, store, timing
from .contracts import validate
from .watch import watch_status


def read_frontmatter(path):
    """Minimal YAML frontmatter reader for this bundle: scalars, one level of nesting, lists of scalars."""
    text = Path(path).read_text(encoding="utf-8")
    m = re.match(r"^---\n(.*?)\n---\n(.*)$", text, re.S)
    if not m:
        return {}, text
    meta, parent = {}, None
    for line in m.group(1).splitlines():
        if not line.strip():
            continue
        if line.startswith("  - ") and parent:
            if not isinstance(meta[parent], list):
                meta[parent] = []
            meta[parent].append(line[4:].strip().strip('"'))
        elif line.startswith("  ") and parent:
            k, _, v = line.strip().partition(":")
            meta[parent][k] = v.strip().strip('"')
        else:
            k, _, v = line.partition(":")
            v = v.strip().strip('"')
            meta[k], parent = (v, None) if v else ({}, k)
    return meta, m.group(2)


COUNTRY_ORDER = ["united-states", "israel", "iran"]


def calibration_bands(accuracy, label="Ceasefire and strike markets", horizon="7"):
    """The backtest's calibration bands used to adjust ladder prices, or None."""
    if not accuracy:
        return None
    for s in accuracy["summary"]:
        if s["label"] == label:
            return s["horizons"].get(horizon, {}).get("calibration")
    return None


def _load_json_folder(folder, schema=None, root=ROOT):
    out = []
    for path in sorted(Path(folder).glob("*.json")):
        record = json.loads(path.read_text(encoding="utf-8"))
        out.append(validate(record, schema, root) if schema else record)
    return out


def build(root=ROOT, now=None, out_path=None):
    root = Path(root)
    now = now or datetime.now(timezone.utc)
    live, demo = forecasts.load_all(root)
    evidence = _load_json_folder(root / "data" / "evidence", "evidence", root)
    observations = store.load(root, days=10, now=now)
    observations.sort(key=lambda o: o.get("published_at") or o["observed_at"], reverse=True)
    sources = json.loads((root / "config" / "sources.json").read_text(encoding="utf-8"))

    countries = []
    for profile in sorted((root / "countries").glob("*/profile.md")):
        meta, body = read_frontmatter(profile)
        stale_after = meta.get("stale_after")
        countries.append({
            "id": meta.get("country", profile.parent.name), "title": meta.get("title"),
            "status": meta.get("status"), "refreshed": (meta.get("generated") or {}).get("at"),
            "stale_after": stale_after, "is_stale": bool(stale_after and stale_after < now.date().isoformat()),
            "sources": meta.get("sources") or [], "body": body,
        })
    countries.sort(key=lambda c: COUNTRY_ORDER.index(c["id"]) if c["id"] in COUNTRY_ORDER else 99)

    accuracy = backtest.load(root)
    reactions = eventstudy.load(root)
    timing_board = timing.board(root, now, calibration_bands(accuracy))
    view = outlook.build(live, timing_board, reactions, evidence, root, now)

    def fc_view(f):
        return {**f, "current_probability": forecasts.current_probability(f)}

    data = {
        "generated_at": now.replace(microsecond=0).isoformat(),
        "countries": countries,
        "forecasts": {
            "live": [fc_view(f) for f in live],
            "demo": [fc_view(f) for f in demo],
            "overdue": scoring.overdue(live, now),
        },
        "scorecard": {"live": scoring.scorecard(live), "demo": scoring.scorecard(demo)},
        "watch": watch_status(observations, now),
        "feed": [o for o in observations if o["collector"] in ("rss", "telegram")][:400],
        "signals": [o for o in observations if o["collector"] in ("adsb", "fleet", "advisory", "gpsjam")][:100],
        "markets": markets.board(root, now),
        "accuracy": accuracy,
        "reactions": reactions,
        "timing": timing_board,
        "outlook": view,
        "polls": polls.load_all(root),
        "baserates": baserates.load_all(root),
        "scenarios": _load_json_folder(root / "data" / "scenarios"),
        "timeline": sorted(_load_json_folder(root / "data" / "timeline", "event", root),
                           key=lambda e: e["date"], reverse=True),
        "relationships": _load_json_folder(root / "data" / "relationships", "relationship", root),
        "evidence": evidence,
        "sources": sources,
        "counts": {"observations_10d": len(observations), "evidence": len(evidence),
                   "live_forecasts": len(live), "demo_forecasts": len(demo)},
    }
    out_path = Path(out_path) if out_path else root / "dashboard" / "data.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    outlook.write_brief(view, out_path.parent.parent if out_path.parent.name == "dashboard" else root)
    return data
