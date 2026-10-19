"""Track Polymarket prices over time as the crowd baseline for every forecast."""

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from . import ROOT
from .collectors.http import fetch_text
from .contracts import validate

GAMMA_URL = "https://gamma-api.polymarket.com/markets?slug={slug}"


def load_watchlist(root=ROOT):
    return json.loads((Path(root) / "config" / "markets.json").read_text(encoding="utf-8"))["markets"]


def price_from_market(market, outcome_index=0):
    prices = market.get("outcomePrices")
    if isinstance(prices, str):
        prices = json.loads(prices)
    if not prices or outcome_index >= len(prices):
        return None
    p = float(prices[outcome_index])
    return p if 0 <= p <= 1 else None


def snapshot(entry, at, fetch=fetch_text, root=ROOT):
    markets = json.loads(fetch(GAMMA_URL.format(slug=entry["slug"])))
    if not markets:
        raise LookupError(f"no market with slug {entry['slug']}")
    m = markets[0]
    p = price_from_market(m, entry.get("outcome_index", 0))
    if p is None:
        raise LookupError(f"{entry['slug']}: no price for outcome {entry.get('outcome_index', 0)}")
    volume = m.get("volumeNum", m.get("volume"))
    return validate({
        "slug": entry["slug"], "source": "polymarket", "at": at, "probability": p,
        "question": m.get("question") or entry["label"], "end_date": (m.get("endDate") or "")[:10] or None,
        "volume": float(volume) if volume not in (None, "") else None, "closed": bool(m.get("closed")),
    }, "market_price", root)


def collect(root=ROOT, fetch=fetch_text, now=None):
    at = (now or datetime.now(timezone.utc)).replace(microsecond=0).isoformat()
    rows, report = [], []
    for entry in load_watchlist(root):
        try:
            rows.append(snapshot(entry, at, fetch, root))
            report.append({"source": f"polymarket:{entry['slug'][:40]}", "ok": True, "items": 1, "flagged": 0})
        except Exception as exc:  # noqa: BLE001
            report.append({"source": f"polymarket:{entry['slug'][:40]}", "ok": False, "error": f"{type(exc).__name__}: {exc}"})
    return rows, report


def save(rows, root=ROOT):
    folder = Path(root) / "data" / "markets"
    folder.mkdir(parents=True, exist_ok=True)
    for row in rows:
        with open(folder / f"{row['at'][:10]}.jsonl", "a", encoding="utf-8") as fh:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    return len(rows)


def history(root=ROOT, days=90, now=None):
    """slug -> list of (at, probability), oldest first."""
    folder = Path(root) / "data" / "markets"
    out = {}
    if not folder.exists():
        return out
    cutoff = ((now or datetime.now(timezone.utc)) - timedelta(days=days)).date().isoformat()
    for f in sorted(folder.glob("*.jsonl")):
        if f.stem < cutoff:
            continue
        for line in f.read_text(encoding="utf-8").splitlines():
            if line.strip():
                row = json.loads(line)
                out.setdefault(row["slug"], []).append(row)
    for rows in out.values():
        rows.sort(key=lambda r: r["at"])
    return out


def board(root=ROOT, now=None):
    """Watchlist joined with latest price and change since the first snapshot in range."""
    hist = history(root, now=now)
    out = []
    for entry in load_watchlist(root):
        rows = hist.get(entry["slug"], [])
        latest = rows[-1] if rows else None
        out.append({
            **entry,
            "url": f"https://polymarket.com/market/{entry['slug']}",
            "question": latest["question"] if latest else None,
            "probability": latest["probability"] if latest else None,
            "as_of": latest["at"] if latest else None,
            "end_date": latest["end_date"] if latest else None,
            "change": (latest["probability"] - rows[0]["probability"]) if len(rows) > 1 else None,
            "series": [[r["at"], r["probability"]] for r in rows[-60:]],
        })
    return out
