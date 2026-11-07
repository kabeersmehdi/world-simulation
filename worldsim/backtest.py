"""How accurate has the crowd been? Score resolved Polymarket markets on our topics.

For each resolved yes/no market, take the price N days before it closed and
compare it with the outcome. This tests the baseline every forecast here is
measured against. Ladder markets on one event are correlated, so the
effective sample is smaller than the market count; the summary says so.
"""

import json
import random
import time
import urllib.parse
from datetime import datetime, timedelta, timezone
from pathlib import Path

from . import ROOT
from .collectors.http import fetch_text
from .scoring import brier

SEARCH_URL = "https://gamma-api.polymarket.com/public-search?q={q}&limit_per_type=50&events_status=closed"
HISTORY_URL = "https://clob.polymarket.com/prices-history?market={token}&interval=max&fidelity=720"
HORIZONS = (30, 7, 1)
SETTLED = 0.02  # a final price within this of 0 or 1 counts as resolved


def load_config(root=ROOT):
    return json.loads((Path(root) / "config" / "backtest.json").read_text(encoding="utf-8"))


def outcome_of(market):
    prices = market.get("outcomePrices")
    if isinstance(prices, str):
        prices = json.loads(prices)
    if not prices or len(prices) != 2:
        return None
    yes = float(prices[0])
    if yes >= 1 - SETTLED:
        return True
    if yes <= SETTLED:
        return False
    return None


def close_time(market):
    """The earlier of the scheduled end and the actual close, in UTC.

    A market that resolves early closes before its end date; one that settles
    late closes after it. The earlier time keeps post-event prices out.
    """
    times = []
    for key in ("closedTime", "endDate"):
        value = market.get(key)
        if value:
            try:
                times.append(datetime.fromisoformat(value[:19].replace(" ", "T")).replace(tzinfo=timezone.utc))
            except ValueError:
                continue
    return min(times) if times else None


def price_before(history, when):
    """Last price at or before `when` (unix seconds). None if the market had not opened."""
    best = None
    for point in history:
        if point["t"] <= when:
            best = point["p"]
        else:
            break
    return best


def find_markets(cfg, fetch=fetch_text):
    found = {}
    for q in cfg["queries"]:
        data = json.loads(fetch(SEARCH_URL.format(q=urllib.parse.quote(q))))
        for event in data.get("events", []):
            for m in event.get("markets", []):
                if m.get("closed") and m.get("slug") and m["slug"] not in found:
                    found[m["slug"]] = {**m, "_event": event.get("title", "")}
    return list(found.values())


def score_market(m, history):
    outcome = outcome_of(m)
    closed = close_time(m)
    if outcome is None or closed is None or not history:
        return None
    row = {"slug": m["slug"], "question": m.get("question", ""), "event": m.get("_event", ""),
           "closed": closed.date().isoformat(), "outcome": outcome,
           "volume": float(m.get("volumeNum") or 0)}
    for h in HORIZONS:
        p = price_before(history, (closed - timedelta(days=h)).timestamp())
        row[f"p{h}"] = p
    return row


def summarize(rows, label):
    out = {"label": label, "markets": len(rows), "events": len({r["event"] for r in rows}),
           "yes_share": (sum(r["outcome"] for r in rows) / len(rows)) if rows else None, "horizons": {}}
    for h in HORIZONS:
        scored = [r for r in rows if r.get(f"p{h}") is not None]
        if not scored:
            out["horizons"][str(h)] = {"n": 0}
            continue
        yes_share = sum(r["outcome"] for r in scored) / len(scored)
        bands = []
        for i in range(10):
            lo, hi = i / 10, (i + 1) / 10
            b = [r for r in scored if lo <= r[f"p{h}"] < hi or (i == 9 and r[f"p{h}"] == 1)]
            bands.append({"band": f"{int(lo * 100)}-{int(hi * 100)}%", "count": len(b),
                          "mean_price": sum(r[f"p{h}"] for r in b) / len(b) if b else None,
                          "happened": sum(r["outcome"] for r in b) / len(b) if b else None})
        out["horizons"][str(h)] = {
            "n": len(scored),
            "market_brier": sum(brier(r[f"p{h}"], r["outcome"]) for r in scored) / len(scored),
            "coin_flip_brier": 0.25,
            "base_rate_brier": sum(brier(yes_share, r["outcome"]) for r in scored) / len(scored),
            "hit_rate": sum((r[f"p{h}"] >= 0.5) == r["outcome"] for r in scored) / len(scored),
            "calibration": bands,
        }
    return out


def calibration_error(rows, h):
    """Count-weighted gap between average price and how often it happened, over ten price bands."""
    scored = [r for r in rows if r.get(f"p{h}") is not None]
    if not scored:
        return None
    gap = 0.0
    for i in range(10):
        b = [r for r in scored if i / 10 <= r[f"p{h}"] < (i + 1) / 10 or (i == 9 and r[f"p{h}"] == 1)]
        if b:
            gap += len(b) * abs(sum(r[f"p{h}"] for r in b) / len(b) - sum(r["outcome"] for r in b) / len(b))
    return gap / len(scored)


def _bucket_stats(rows):
    out = {}
    for h in HORIZONS:
        scored = [r for r in rows if r.get(f"p{h}") is not None]
        if not scored:
            out[str(h)] = {"n": 0}
            continue
        out[str(h)] = {
            "n": len(scored), "events": len({r["event"] for r in scored}),
            "market_brier": sum(brier(r[f"p{h}"], r["outcome"]) for r in scored) / len(scored),
            "calibration_error": calibration_error(scored, h),
            "hit_rate": sum((r[f"p{h}"] >= 0.5) == r["outcome"] for r in scored) / len(scored),
            "yes_share": sum(r["outcome"] for r in scored) / len(scored),
            **_longshot(scored, h),
        }
    return out


def _longshot(rows, h, cut=0.3):
    """Signed gap (price minus how often it happened) for long shots under `cut` and favorites over 1 - cut.

    A positive long-shot gap means the crowd paid too much for unlikely
    outcomes, the classic favorite-longshot bias.
    """
    out = {}
    for name, part in (("longshot", [r for r in rows if r[f"p{h}"] < cut]),
                       ("favorite", [r for r in rows if r[f"p{h}"] > 1 - cut])):
        out[f"{name}_n"] = len(part)
        out[f"{name}_gap"] = (sum(r[f"p{h}"] for r in part) - sum(r["outcome"] for r in part)) / len(part) if part else None
    return out


def _resample(rows, rng):
    """Draw whole events with replacement, so ladder markets on one event stay together."""
    by_event = {}
    for r in rows:
        by_event.setdefault(r["event"], []).append(r)
    events = list(by_event)
    return [r for _ in events for r in by_event[rng.choice(events)]]


def by_volume(rows, buckets=4, draws=1000, seed=7):
    """Split resolved markets into equal-size volume buckets and compare thin with thick.

    The thin-minus-thick gaps come with a 95% range from an event-level
    bootstrap. A range that crosses zero means no clear difference.
    """
    rows = sorted(rows, key=lambda r: r["volume"])
    size = len(rows) / buckets
    groups = [rows[int(i * size):int((i + 1) * size)] for i in range(buckets)]
    out = {"buckets": [], "thin_vs_thick": {}}
    for i, g in enumerate(groups):
        if not g:
            continue
        lo, hi = g[0]["volume"], g[-1]["volume"]
        out["buckets"].append({"label": f"Volume bucket {i + 1} of {buckets} (${lo:,.0f} to ${hi:,.0f})",
                               "min_volume": lo, "max_volume": hi, "markets": len(g),
                               "events": len({r["event"] for r in g}), "horizons": _bucket_stats(g)})
    thin, thick = groups[0], groups[-1]
    rng = random.Random(seed)
    for h in HORIZONS:
        t_rows = [r for r in thin if r.get(f"p{h}") is not None]
        k_rows = [r for r in thick if r.get(f"p{h}") is not None]
        if not t_rows or not k_rows:
            out["thin_vs_thick"][str(h)] = None
            continue

        def gaps(a, b):
            ce = calibration_error(a, h) - calibration_error(b, h)
            br = (sum(brier(r[f"p{h}"], r["outcome"]) for r in a) / len(a)
                  - sum(brier(r[f"p{h}"], r["outcome"]) for r in b) / len(b))
            ls_a, ls_b = _longshot(a, h)["longshot_gap"], _longshot(b, h)["longshot_gap"]
            return ce, br, (ls_a - ls_b) if ls_a is not None and ls_b is not None else None, ls_a

        ce, br, ls, thin_ls = gaps(t_rows, k_rows)
        sims = [gaps(_resample(t_rows, rng), _resample(k_rows, rng)) for _ in range(draws)]
        lo, hi = 0.025, 0.975

        def ci(i):
            xs = sorted(x[i] for x in sims if x[i] is not None)
            return [xs[int(lo * len(xs))], xs[int(hi * len(xs)) - 1]] if xs else None

        out["thin_vs_thick"][str(h)] = {"calibration_error_diff": ce, "calibration_error_ci": ci(0),
                                        "brier_diff": br, "brier_ci": ci(1),
                                        "longshot_gap_diff": ls, "longshot_gap_ci": ci(2),
                                        "thin_longshot_gap": thin_ls, "thin_longshot_gap_ci": ci(3)}
    return out


def by_volume_from_file(root=ROOT, buckets=4):
    path = Path(root) / "data" / "backtests" / "polymarket-geopolitics.json"
    if not path.exists():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    result = {"source_run_at": data["run_at"], "min_volume": data["min_volume"],
              "note": "Equal-size buckets by dollars traded. Calibration error is the count-weighted gap between average price and how often the event happened, across ten price bands. Thin-minus-thick ranges come from resampling whole events.",
              **by_volume(data["rows"], buckets)}
    out = Path(root) / "data" / "backtests" / "by-volume.json"
    out.write_text(json.dumps(result, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    return result


def run(root=ROOT, fetch=fetch_text, now=None, pause=0.15):
    cfg = load_config(root)
    candidates = [m for m in find_markets(cfg, fetch) if float(m.get("volumeNum") or 0) >= cfg["min_volume"]]
    rows = []
    for m in candidates:
        tokens = m.get("clobTokenIds")
        tokens = json.loads(tokens) if isinstance(tokens, str) else tokens
        if not tokens or outcome_of(m) is None:
            continue
        try:
            history = json.loads(fetch(HISTORY_URL.format(token=tokens[0]))).get("history", [])
        except Exception:  # noqa: BLE001 - a missing history skips one market only
            continue
        row = score_market(m, sorted(history, key=lambda p: p["t"]))
        if row:
            rows.append(row)
        if pause:
            time.sleep(pause)
    rows.sort(key=lambda r: r["closed"], reverse=True)
    words = cfg["ceasefire_words"]
    ceasefire = [r for r in rows if any(w in r["question"].lower() for w in words)]
    result = {
        "run_at": (now or datetime.now(timezone.utc)).replace(microsecond=0).isoformat(),
        "queries": cfg["queries"], "min_volume": cfg["min_volume"],
        "note": "Prices taken 30, 7 and 1 days before each market closed. Ladder markets on one event move together, so the number of events is the fairer sample size. The 1-day price can already reflect the news that resolved the market.",
        "summary": [summarize(rows, "All resolved geopolitics markets"), summarize(ceasefire, "Ceasefire and strike markets")],
        "rows": rows,
    }
    out = Path(root) / "data" / "backtests" / "polymarket-geopolitics.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    return result


def load(root=ROOT):
    path = Path(root) / "data" / "backtests" / "polymarket-geopolitics.json"
    if not path.exists():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    return {k: v for k, v in data.items() if k != "rows"} | {"recent": data["rows"][:60]}
