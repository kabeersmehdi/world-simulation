"""Turn a ladder of dated markets into a "when" curve.

Two ladder kinds:
- survival:   each market is "X still holds through date d" (a ceasefire continuing)
- cumulative: each market is "X happens by date d" (a deal, a blockade lifted)

Both become P(event has happened by d). The event is the break for a survival
ladder and the thing itself for a cumulative one. Prices from separate markets
can disagree with each other, so the curve is made monotone before use.
"""

import json
from datetime import date, datetime, timezone
from pathlib import Path

from . import ROOT, markets
from .collectors.http import fetch_text


def load_ladders(root=ROOT):
    return json.loads((Path(root) / "config" / "ladders.json").read_text(encoding="utf-8"))["ladders"]


def monotone_increasing(values):
    """Pool-adjacent-violators: closest non-decreasing sequence, equal weights."""
    blocks = []  # [sum, count]
    for v in values:
        blocks.append([v, 1])
        while len(blocks) > 1 and blocks[-2][0] / blocks[-2][1] > blocks[-1][0] / blocks[-1][1]:
            s, c = blocks.pop()
            blocks[-1][0] += s
            blocks[-1][1] += c
    out = []
    for s, c in blocks:
        out.extend([s / c] * c)
    return out


def curve(ladder, prices, today):
    """prices: slug -> probability of the market's Yes. Returns the timing summary."""
    steps = sorted(ladder["steps"], key=lambda s: s["date"])
    steps = [s for s in steps if s["slug"] in prices and s["date"] >= today.isoformat()]
    raw = []
    for s in steps:
        p = prices[s["slug"]]
        raw.append(1 - p if ladder["kind"] == "survival" else p)
    happened = monotone_increasing(raw)
    rows, prev_date, prev_p = [], today, 0.0
    for s, r, h in zip(steps, raw, happened):
        rows.append({
            "from": prev_date.isoformat(), "to": s["date"], "slug": s["slug"],
            "market_yes": prices[s["slug"]], "by_date": h, "raw_by_date": r,
            "in_window": max(h - prev_p, 0.0),
        })
        prev_date, prev_p = date.fromisoformat(s["date"]), h
    return {
        "id": ladder["id"], "title": ladder["title"], "kind": ladder["kind"], "event": ladder["event"],
        "as_of": today.isoformat(), "rows": rows,
        "after_last": max(1 - prev_p, 0.0),
        "median_date": median_date(today, rows),
        "adjusted": any(abs(r["by_date"] - r["raw_by_date"]) > 1e-9 for r in rows),
    }


def median_date(today, rows):
    """Date the curve crosses 50%, by straight-line interpolation. None if it never does."""
    prev_d, prev_p = today, 0.0
    for r in rows:
        d, p = date.fromisoformat(r["to"]), r["by_date"]
        if p >= 0.5:
            if p == prev_p:
                return d.isoformat()
            frac = (0.5 - prev_p) / (p - prev_p)
            return date.fromordinal(prev_d.toordinal() + round(frac * (d.toordinal() - prev_d.toordinal()))).isoformat()
        prev_d, prev_p = d, p
    return None


def collect(root=ROOT, fetch=fetch_text, now=None):
    """Snapshot every ladder market into data/markets. Returns (rows, report)."""
    at = (now or datetime.now(timezone.utc)).replace(microsecond=0).isoformat()
    rows, report = [], []
    for ladder in load_ladders(root):
        for step in ladder["steps"]:
            entry = {"slug": step["slug"], "label": f"{ladder['title']} ({step['date']})", "outcome_index": 0}
            try:
                rows.append(markets.snapshot(entry, at, fetch, root))
                report.append({"source": f"ladder:{step['slug'][:40]}", "ok": True, "items": 1, "flagged": 0})
            except Exception as exc:  # noqa: BLE001
                report.append({"source": f"ladder:{step['slug'][:40]}", "ok": False, "error": f"{type(exc).__name__}: {exc}"})
    return rows, report


def board(root=ROOT, now=None, bands=None):
    """Every ladder's curve from the latest saved prices, plus a calibrated column when bands are given."""
    now = now or datetime.now(timezone.utc)
    hist = markets.history(root, now=now)
    latest = {slug: rows[-1]["probability"] for slug, rows in hist.items() if rows}
    return [with_calibration(curve(l, latest, now.date()), bands) for l in load_ladders(root)]


SHRINK = 30  # band count at which the past calibration gets half the weight


def calibrate(p, bands):
    """Map a market price to how often such prices actually came true.

    Uses the backtest's calibration bands (mean price -> share that happened),
    interpolated, then shrunk toward the raw price by band size so thin bands
    barely move it. Returns p unchanged when there is no backtest.
    """
    pts = sorted((b["mean_price"], b["happened"], b["count"]) for b in bands or [] if b.get("count"))
    if len(pts) < 2:
        return p
    if p <= pts[0][0]:
        x0, y0, n = pts[0]
        target, count = y0, n
    elif p >= pts[-1][0]:
        x0, y0, n = pts[-1]
        target, count = y0, n
    else:
        for (x0, y0, n0), (x1, y1, n1) in zip(pts, pts[1:]):
            if x0 <= p <= x1:
                w = (p - x0) / (x1 - x0) if x1 > x0 else 0
                target, count = y0 + w * (y1 - y0), n0 + w * (n1 - n0)
                break
    weight = count / (count + SHRINK)
    return min(max(p + weight * (target - p), 0.0), 1.0)


def with_calibration(summary, bands):
    """Add a calibrated column to a curve, applied to each market's Yes price."""
    if not bands:
        summary["calibrated"] = None
        return summary
    probs = []
    for r in summary["rows"]:
        yes = calibrate(r["market_yes"], bands)
        probs.append(1 - yes if summary["kind"] == "survival" else yes)
    probs = monotone_increasing(probs)
    prev = 0.0
    for r, p in zip(summary["rows"], probs):
        r["calibrated_by_date"] = p
        r["calibrated_in_window"] = max(p - prev, 0.0)
        prev = p
    summary["calibrated"] = {
        "after_last": max(1 - prev, 0.0) if probs else None,
        "median_date": median_date(date.fromisoformat(summary["as_of"]),
                                   [{"to": r["to"], "by_date": r["calibrated_by_date"]} for r in summary["rows"]]),
    }
    return summary
