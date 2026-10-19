"""How did markets actually move after past strikes?

For each strike or war event in data/timeline, and each asset in
config/assets.json:
- base = the last close strictly before the event date
- day k = the k-th trading close on or after the event date
- move = percent change from base to day k (for SPY-benchmarked stocks, also
  the move minus SPY's move over the same days)

Each average move is compared with the asset's normal k-day swing over the
whole sample (the standard deviation of all k-day moves). A reaction only
counts as unusual when it is clearly bigger than that ordinary noise. With
a handful of events, even that is a hint, not proof.
"""

import json
import math
import statistics
from datetime import datetime, timezone
from pathlib import Path

from . import ROOT, prices
from .contracts import validate

WINDOWS = (1, 5, 20)
EVENT_CATEGORIES = ("strike", "war")
UNUSUAL_Z = 2.0  # average move at least this many standard errors from zero
ROBUST_SHARE = 0.5  # still at least half as big, same direction, once the biggest event is dropped


def move(rows, event_day, k):
    """Percent move from the close before event_day to the k-th close on or after it."""
    i = prices.first_index_on_or_after(rows, event_day)
    if i is None or i == 0 or i + k - 1 >= len(rows):
        return None
    base = rows[i - 1][1]
    return (rows[i + k - 1][1] / base - 1) * 100


def typical_swing(rows, k):
    """Standard deviation of all k-day percent moves in the sample."""
    moves = [(rows[j + k][1] / rows[j][1] - 1) * 100 for j in range(len(rows) - k)]
    return statistics.pstdev(moves) if len(moves) > 2 else None


def holds(s):
    """Unusual, and still at least ROBUST_SHARE as big in the same direction without the biggest event."""
    return bool(s["unusual"] and s["mean_without_largest"] is not None
                and s["mean_without_largest"] * s["mean"] > 0
                and abs(s["mean_without_largest"]) >= ROBUST_SHARE * abs(s["mean"]))


def load_events(root=ROOT):
    events = []
    for path in sorted((Path(root) / "data" / "timeline").glob("*.json")):
        e = validate(json.loads(path.read_text(encoding="utf-8")), "event", root)
        if e["category"] in EVENT_CATEGORIES:
            events.append(e)
    events.sort(key=lambda e: (e["date"], e["id"]))
    unique, seen = [], set()
    for e in events:  # two entries on one date are one market event
        if e["date"] not in seen:
            seen.add(e["date"])
            unique.append(e)
    return unique


def run(root=ROOT, now=None):
    cfg = prices.load_config(root)
    events = load_events(root)
    series = {a["ticker"]: prices.load(a["ticker"], root) for a in cfg["assets"]}
    spy = series.get("SPY")
    assets_out = []
    for asset in cfg["assets"]:
        rows = series.get(asset["ticker"])
        if not rows:
            continue
        bench = spy if asset.get("benchmark") == "SPY" and spy else None
        per_event, summary = [], {}
        for e in events:
            entry = {"event_id": e["id"], "date": e["date"], "title": e["title"]}
            for k in WINDOWS:
                m = move(rows, e["date"], k)
                entry[f"d{k}"] = round(m, 2) if m is not None else None
                if bench is not None and m is not None:
                    b = move(bench, e["date"], k)
                    entry[f"x{k}"] = round(m - b, 2) if b is not None else None
            per_event.append(entry)
        for k in WINDOWS:
            key = f"x{k}" if bench is not None else f"d{k}"
            vals = [p[key] for p in per_event if p.get(key) is not None]
            swing = typical_swing(rows, k)
            mean = statistics.mean(vals) if vals else None
            z = (mean / (swing / math.sqrt(len(vals)))) if vals and swing else None
            trimmed = sorted(vals, key=abs)[:-1] if len(vals) > 2 else []
            summary[str(k)] = {
                "n": len(vals), "measure": "vs SPY" if bench is not None else "raw",
                "mean": round(mean, 2) if mean is not None else None,
                "mean_without_largest": round(statistics.mean(trimmed), 2) if trimmed else None,
                "median": round(statistics.median(vals), 2) if vals else None,
                "share_up": round(sum(v > 0 for v in vals) / len(vals), 2) if vals else None,
                "typical_swing": round(swing, 2) if swing else None,
                "z": round(z, 2) if z is not None else None,
                "unusual": bool(z is not None and abs(z) >= UNUSUAL_Z and len(vals) >= 3),
            }
            summary[str(k)]["holds_without_largest"] = holds(summary[str(k)])
        assets_out.append({**{k: asset[k] for k in ("ticker", "name", "category", "why")},
                           "benchmark": asset.get("benchmark"), "first_date": rows[0][0], "last_date": rows[-1][0],
                           "summary": summary, "events": per_event})
    result = {
        "run_at": (now or datetime.now(timezone.utc)).replace(microsecond=0).isoformat(),
        "windows": list(WINDOWS),
        "events": [{"id": e["id"], "date": e["date"], "title": e["title"], "category": e["category"]} for e in events],
        "note": ("Base is the last close before the event date; day k is the k-th trading close on or after it. "
                 "US-listed stocks are shown against SPY. 'Unusual' means the average move is at least "
                 f"{UNUSUAL_Z} standard errors from zero given the asset's normal swing, with 3 or more events. "
                 "Events on the same date count once. Some events fall inside each other's 5- and 20-day windows, which overstates certainty. "
                 "'Without largest' drops the single biggest move to show whether one event carries the average. "
                 "A few events, so treat every number as a hint. Not a trading signal."),
        "assets": assets_out,
    }
    out = Path(root) / "data" / "eventstudy" / "strike-reactions.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    return result


def load(root=ROOT):
    path = Path(root) / "data" / "eventstudy" / "strike-reactions.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None
