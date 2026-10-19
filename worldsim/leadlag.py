"""Do the indicators move before Polymarket does? A lead-lag test.

For each indicator, take its onsets: the first firing after a quiet spell, so
a day of nonstop Home Front Command posts counts once. For every onset and
every market open at that moment, measure how far the price moved in the next
1, 6, 24 and 72 hours, and how far it had already moved in the same span
before the onset.

The baseline is the same measurement at random times. Each random draw moves
every onset to a random moment inside its own source's coverage and keeps the
same markets rule, so busy war months and quiet months are weighed alike. The
p-value is the share of draws whose average move is at least as big as the
real one.

Reading it:
  after >> random, before ~ random   the indicator leads (a possible edge)
  after ~ before >> random           both react to the same news (no edge)
  1-hour move already holds most     the market reacts within the hour; the
  of the 6-hour move                 hourly price data cannot show a lead
"""

import json
import random
import re
import time
import urllib.parse
from datetime import datetime, timedelta, timezone
from pathlib import Path

from . import ROOT, backfill, backtest, markets, store
from .collectors.http import fetch_text
from .contracts import parse_datetime

GAMMA_URL = "https://gamma-api.polymarket.com/markets?slug={slug}"
HISTORY_URL = "https://clob.polymarket.com/prices-history?market={token}&startTs={start}&endTs={end}&fidelity=60"
CHUNK = 10 * 86400  # the price API refuses hourly windows much longer than this
HOUR = 3600


def load_config(root=ROOT):
    return json.loads((Path(root) / "config" / "leadlag.json").read_text(encoding="utf-8"))


# ---------- indicator side ----------

def _ts(value):
    return parse_datetime(value).timestamp()


def live_firings(root=ROOT):
    """Firings from the live log (data/observations), timed by publication when known."""
    out = []
    for ob in store.load(root=root, days=None):
        if ob["indicators"]:
            out.append({"source_id": ob["source_id"], "key": ob["id"],
                        "at": ob.get("published_at") or ob["observed_at"], "indicators": ob["indicators"]})
    return out


def live_coverage(root=ROOT):
    """Each live source's covered span: first to last observation saved."""
    spans = {}
    for ob in store.load(root=root, days=None):
        t = _ts(ob["observed_at"])
        lo, hi = spans.get(ob["source_id"], (t, t))
        spans[ob["source_id"]] = (min(lo, t), max(hi, t))
    return spans


def onsets(firings, quiet_hours):
    """indicator -> sorted [(time, source_id)] keeping only firings after `quiet_hours` of silence."""
    by_ind = {}
    for f in firings:
        for ind in f["indicators"]:
            by_ind.setdefault(ind, []).append((_ts(f["at"]), f["source_id"]))
    out = {}
    for ind, items in by_ind.items():
        items.sort()
        kept, last = [], None
        for t, sid in items:
            if last is None or t - last >= quiet_hours * HOUR:
                kept.append((t, sid))
            last = t
        out[ind] = kept
    return out


# ---------- market side ----------

def price_history(token, start, end, fetch=fetch_text, pause=0.1):
    """Hourly prices between two unix times, fetched in 10-day windows."""
    points, t, end = {}, int(start), int(end)
    while t < end:
        stop = min(end, t + CHUNK)
        data = json.loads(fetch(HISTORY_URL.format(token=token, start=t, end=stop)))
        for p in data.get("history", []):
            if t <= p["t"] <= stop:  # the API tacks today's price onto every answer
                points[p["t"]] = p["p"]
        t = stop
        if pause:
            time.sleep(pause)
    return [{"t": k, "p": points[k]} for k in sorted(points)]


def market_meta(slug, outcome_index=0, fetch=fetch_text):
    found = json.loads(fetch(GAMMA_URL.format(slug=urllib.parse.quote(slug))))
    if not found:
        found = json.loads(fetch(GAMMA_URL.format(slug=urllib.parse.quote(slug)) + "&closed=true"))
    if not found:
        raise LookupError(f"no market with slug {slug}")
    m = found[0]
    tokens = m.get("clobTokenIds")
    tokens = json.loads(tokens) if isinstance(tokens, str) else tokens
    opened = m.get("startDate") or m.get("createdAt")
    closed = backtest.close_time(m) if m.get("closed") else None
    return {"slug": slug, "question": m.get("question", ""), "token": tokens[outcome_index],
            "volume": float(m.get("volumeNum") or 0), "opened": opened,
            "closed": closed.isoformat() if closed else None}


def study_markets(root=ROOT, cfg=None):
    """The watchlist's security markets plus resolved security markets from the backtest."""
    cfg = cfg or load_config(root)
    picked = [{"slug": m["slug"], "outcome_index": m.get("outcome_index", 0), "origin": "watchlist"}
              for m in markets.load_watchlist(root) if m["topic"] in cfg["topics"]]
    extra = cfg.get("from_backtest")
    path = Path(root) / "data" / "backtests" / "polymarket-geopolitics.json"
    if extra and path.exists():
        words, places = extra["words"], re.compile(extra["places"])
        seen = {m["slug"] for m in picked}
        for r in json.loads(path.read_text(encoding="utf-8"))["rows"]:
            q = r["question"].lower()
            if (r["closed"] >= cfg["since"] and r["slug"] not in seen and any(w in q for w in words) and places.search(q)):
                seen.add(r["slug"])
                picked.append({"slug": r["slug"], "outcome_index": 0, "origin": "resolved"})
    return picked


def _cache(root):
    return Path(root) / "data" / "leadlag" / "prices"


def fetch_markets(root=ROOT, fetch=fetch_text, now=None, pause=0.1, log=print):
    """Fetch (or read cached) hourly histories. Returns slug -> {meta, history}."""
    cfg = load_config(root)
    now = now or datetime.now(timezone.utc)
    since = datetime.fromisoformat(cfg["since"]).replace(tzinfo=timezone.utc).timestamp()
    folder = _cache(root)
    folder.mkdir(parents=True, exist_ok=True)
    out, failed = {}, 0
    for entry in study_markets(root, cfg):
        path = folder / f"{entry['slug'][:120]}.json"
        if path.exists():
            cached = json.loads(path.read_text(encoding="utf-8"))
            if cached["meta"]["closed"] or cached.get("fetched_at", "") >= (now - timedelta(hours=6)).isoformat():
                out[entry["slug"]] = cached
                continue
        try:
            meta = market_meta(entry["slug"], entry["outcome_index"], fetch)
            start = max(since, _ts(meta["opened"])) if meta["opened"] else since
            end = _ts(meta["closed"]) if meta["closed"] else now.timestamp()
            hist = price_history(meta["token"], start, end, fetch, pause)
        except Exception as exc:  # noqa: BLE001 - one market failing skips that market
            failed += 1
            log(f"FAIL {entry['slug'][:60]}: {type(exc).__name__}: {exc}")
            continue
        item = {"meta": {**meta, "origin": entry["origin"]}, "fetched_at": now.isoformat(), "history": hist}
        path.write_text(json.dumps(item) + "\n", encoding="utf-8")
        out[entry["slug"]] = item
    log(f"{len(out)} markets with hourly prices, {failed} failed.")
    return out


# ---------- the test ----------

def hourly(history, t0):
    """(first hour index, prices) with each hour holding the last price at or before it."""
    if len(history) < 2:
        return None
    first = -(-(history[0]["t"] - t0) // HOUR)
    last = (history[-1]["t"] - t0) // HOUR
    prices, j = [], 0
    for i in range(int(first), int(last) + 1):
        edge = t0 + i * HOUR
        while j + 1 < len(history) and history[j + 1]["t"] <= edge:
            j += 1
        prices.append(history[j]["p"])
    return (int(first), prices) if prices else None


def tables(histories, t0, hours, h, big_move):
    """Per onset hour f, summed over every market open from f-h to f+1+h:
    pair count, absolute move before (f-h to f), after (f+1 to f+1+h), and big moves after.

    The onset's own hour is skipped: a collector running every 15 minutes
    sees a firing at best minutes late, so a move inside that hour is not
    one you could have traded.
    """
    cnt, before, after, big = [0] * hours, [0.0] * hours, [0.0] * hours, [0] * hours
    for grid in histories:
        if grid is None:
            continue
        s, p = grid
        for k in range(h, len(p) - 1 - h):
            f = s + k
            if 0 <= f < hours:
                a = abs(p[k + 1 + h] - p[k + 1])
                cnt[f] += 1
                before[f] += abs(p[k] - p[k - h])
                after[f] += a
                big[f] += a >= big_move
    return cnt, before, after, big


def _sums(hours_list, tab):
    cnt, before, after, big = tab
    n = sum(cnt[f] for f in hours_list)
    if not n:
        return 0, None, None, None
    return n, sum(before[f] for f in hours_list) / n, sum(after[f] for f in hours_list) / n, sum(big[f] for f in hours_list) / n


def _mean(xs):
    return sum(xs) / len(xs) if xs else None


def measure(onset_list, histories, coverage, horizons, t0, t1, draws=1000, big_move=0.05, seed=7):
    """Real onsets against `draws` random reshuffles of the same onsets.

    histories are hourly grids from hourly(); t0 and t1 bound the study in unix seconds.
    """
    rng = random.Random(seed)
    hours = int((t1 - t0) // HOUR) + 1
    out = {"onsets": len(onset_list), "horizons": {}}
    for h in horizons:
        tab = tables(histories, t0, hours, h, big_move)
        real = [int((t - t0) // HOUR) for t, _sid in onset_list if t0 <= t <= t1]
        real = [f for f in real if 0 <= f < hours]
        n, mb, ma, mbig = _sums(real, tab)
        row = {"onsets_with_markets": sum(1 for f in real if tab[0][f]), "pairs": n}
        if not n:
            out["horizons"][str(h)] = row
            continue
        rand_after, rand_before, rand_big = [], [], []
        for _ in range(draws):
            fake = []
            for _t, sid in onset_list:
                lo, hi = coverage[sid]
                lo, hi = max(lo, t0) + h * HOUR, min(hi, t1) - h * HOUR
                if hi > lo:
                    fake.append(int((rng.uniform(lo, hi) - t0) // HOUR))
            rn, rb, ra, rbig = _sums(fake, tab)
            if rn:
                rand_after.append(ra)
                rand_before.append(rb)
                rand_big.append(rbig)
        base = _mean(rand_after)
        # Drop the onset that moved markets most: one war day should not carry the result.
        per = sorted(((tab[2][f] / tab[0][f], f) for f in set(real) if tab[0][f]), reverse=True)
        rest = [f for f in real if not per or f != per[0][1]]
        _n, _b, ma_rest, _big = _sums(rest, tab)
        row.update({
            "largest_onset": datetime.fromtimestamp(t0 + per[0][1] * HOUR, timezone.utc).isoformat() if per else None,
            "mean_move_after_without_largest": ma_rest,
            "p_value_without_largest": (1 + sum(m >= ma_rest for m in rand_after)) / (1 + len(rand_after)) if rand_after and ma_rest is not None else None,
            "mean_move_after": ma, "mean_move_before": mb, "mean_move_random": base,
            "after_vs_random": ma / base if base else None,
            "before_vs_random": mb / base if base else None,
            "big_move_share_after": mbig, "big_move_share_random": _mean(rand_big),
            "p_value": (1 + sum(m >= ma for m in rand_after)) / (1 + len(rand_after)) if rand_after else None,
            "p_value_before": (1 + sum(m >= mb for m in rand_before)) / (1 + len(rand_before)) if rand_before else None,
        })
        out["horizons"][str(h)] = row
    return out


def verdict(result, alpha=0.05, min_onsets=10):
    """Plain-English read of one indicator's result."""
    n = result["onsets"]
    rows = {int(h): r for h, r in result["horizons"].items() if r.get("p_value") is not None}
    if not rows:
        return "no onset overlapped an open market"
    if min(r["onsets_with_markets"] for r in rows.values()) < min_onsets:
        return f"too few onsets to judge ({n})"
    lead = [h for h, r in sorted(rows.items()) if r["p_value"] < alpha and r["p_value_before"] >= alpha]
    both = [h for h, r in sorted(rows.items()) if r["p_value"] < alpha and r["p_value_before"] < alpha]
    robust = [h for h in lead if (rows[h].get("p_value_without_largest") or 1) < alpha]
    if robust:
        return f"moves before the market: bigger moves in the {robust[0]} hours after, not before"
    if lead:
        return (f"one event only: bigger moves in the {lead[0]} hours after, but they vanish without "
                f"the largest onset ({rows[lead[0]]['largest_onset'][:16]})")
    if both:
        return "moves with the market: prices were already moving before it fired"
    return "no lead: moves after it fires look like random times"


def run(root=ROOT, fetch=fetch_text, now=None, log=print):
    cfg = load_config(root)
    now = now or datetime.now(timezone.utc)
    since = datetime.fromisoformat(cfg["since"]).replace(tzinfo=timezone.utc).timestamp()
    data = fetch_markets(root, fetch, now, log=log)
    t1 = now.timestamp()
    histories = [hourly(m["history"], since) for m in data.values()]

    cov_file = Path(root) / "data" / "backfill" / "coverage.json"
    coverage = live_coverage(root)
    if cov_file.exists():
        for c in json.loads(cov_file.read_text(encoding="utf-8"))["sources"]:
            if c.get("from") and c.get("to"):
                lo = c["from"] if "T" in c["from"] else datetime.strptime(c["from"], "%Y%m%d").replace(tzinfo=timezone.utc).isoformat()
                hi = c["to"] if "T" in c["to"] else datetime.strptime(c["to"], "%Y%m%d").replace(tzinfo=timezone.utc).isoformat()
                coverage[c["source_id"]] = (max(since, _ts(lo)), _ts(hi))
    firings = [f for f in backfill.load(root) + live_firings(root) if f["source_id"] in coverage and _ts(f["at"]) >= since]
    found = onsets(firings, cfg["quiet_hours"])

    indicators = {}
    for ind in cfg["indicators"]:
        res = measure(found.get(ind, []), histories, coverage, cfg["horizons"], since, t1, cfg["random_draws"], cfg["big_move"])
        res["verdict"] = verdict(res, cfg["alpha"], cfg["min_onsets"])
        res["sources"] = sorted({sid for _t, sid in found.get(ind, [])})
        indicators[ind] = res
    result = {
        "run_at": now.replace(microsecond=0).isoformat(), "since": cfg["since"], "quiet_hours": cfg["quiet_hours"],
        "horizons": cfg["horizons"], "random_draws": cfg["random_draws"], "big_move": cfg["big_move"],
        "markets": {"total": sum(g is not None for g in histories),
                    "watchlist": sum(m["meta"]["origin"] == "watchlist" for m in data.values()),
                    "resolved": sum(m["meta"]["origin"] == "resolved" for m in data.values())},
        "coverage": {sid: [datetime.fromtimestamp(lo, timezone.utc).isoformat(), datetime.fromtimestamp(hi, timezone.utc).isoformat()]
                     for sid, (lo, hi) in sorted(coverage.items())},
        "note": "Moves are absolute changes in the Yes price, in probability points, from hourly Polymarket prices. One onset touches many markets at once, so the onset count is the fair sample size, not the pair count.",
        "indicators": indicators,
        "untested": cfg["untested"],
    }
    out = Path(root) / "data" / "leadlag" / "result.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    return result
