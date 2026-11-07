"""Do the fear gauges move before Polymarket does?

The idea: people who know something hedge first. Oil option prices (OVX),
stock option prices (VIX, SKEW), the seaborne oil premium, gold, the shekel,
defense stocks and tanker stocks all carry that hedging, with a timestamp.
If they jump before the crowd's strike odds move, that is a lead you could act
on. If the crowd was already moving, they are reacting to the same headline.

Method, mirroring worldsim/leadlag.py:
  1. A gauge fires on a trading day its change is at least `big_move_sd` of
     its normal daily swing (trailing `swing_days`), in the fear direction,
     after `quiet_days` trading days without a firing.
  2. The firing is placed at the US close (`close_hour_utc`). The move in each
     open Polymarket strike or ceasefire market is measured from the next full
     hour over each horizon, and the move over the same span before the close.
  3. The baseline draws the same number of random trading days from the same
     gauge's own calendar, at the same close hour, `random_draws` times.
     The p-value is the share of draws with an average move at least as big.
  4. The largest onset is dropped once to see whether one day carries it.

Reads the hourly Polymarket prices the lead-lag test cached, and the daily
closes from `python -m worldsim prices` (fetching the gauges it lacks).
"""

import json
import math
import random
import statistics
from datetime import datetime, timedelta, timezone
from pathlib import Path

from . import ROOT, leadlag, prices
from .collectors.http import fetch_text

HOUR = 3600


def load_config(root=ROOT):
    return json.loads((Path(root) / "config" / "fear.json").read_text(encoding="utf-8"))


def tickers(cfg):
    out = []
    for g in cfg["gauges"]:
        out += [g["ticker"]] if "ticker" in g else g.get("spread") or g.get("ratio") or []
    return sorted(set(out))


def series(gauge, root=ROOT):
    """(date, value) rows for one gauge: a ticker, a spread of two, or a ratio of two."""
    if "ticker" in gauge:
        return prices.load(gauge["ticker"], root)
    a_key, b_key = gauge.get("spread") or gauge["ratio"]
    a, b = prices.load(a_key, root), prices.load(b_key, root)
    if not a or not b:
        return None
    bmap = dict(b)
    if "spread" in gauge:
        return [(d, v - bmap[d]) for d, v in a if d in bmap]
    return [(d, v / bmap[d]) for d, v in a if d in bmap and bmap[d]]


def changes(rows, kind):
    """Daily changes: differences for an index level, log returns for a price."""
    out = []
    for (d0, v0), (d1, v1) in zip(rows, rows[1:]):
        if kind == "level":
            out.append((d1, v1 - v0))
        elif v0 > 0 and v1 > 0:
            out.append((d1, math.log(v1 / v0)))
    return out


def firings(rows, kind, direction, big_move_sd, swing_days, min_history, quiet_days):
    """Dates the gauge fired, and the dates it could have (its calendar once the swing is known)."""
    ch = changes(rows, kind)
    fired, calendar, last_fire = [], [], -10 ** 9
    for i, (d, c) in enumerate(ch):
        window = [x for _, x in ch[max(0, i - swing_days):i]]
        if len(window) < min_history:
            continue
        swing = statistics.pstdev(window)
        calendar.append(d)
        if not swing:
            continue
        z = c / swing * (1 if direction == "up" else -1)
        if z >= big_move_sd and i - last_fire > quiet_days:
            fired.append({"date": d, "swings": round(z, 1)})
            last_fire = i
    return fired, calendar


def _close_ts(day, close_hour):
    return datetime.fromisoformat(day).replace(tzinfo=timezone.utc, hour=close_hour).timestamp()


def _mean(xs):
    return sum(xs) / len(xs) if xs else None


def measure(fired, calendar, histories, horizons, t0, t1, close_hour, draws=1000, big_move=0.05, seed=7):
    """Real firings against random trading days from the same calendar. Same tables as the lead-lag test."""
    rng = random.Random(seed)
    hours = int((t1 - t0) // HOUR) + 1
    real = [int((_close_ts(f["date"], close_hour) - t0) // HOUR) for f in fired]
    real = [f for f in real if 0 <= f < hours]
    pool = [int((_close_ts(d, close_hour) - t0) // HOUR) for d in calendar]
    out = {"onsets": len(fired), "horizons": {}}
    for h in horizons:
        tab = leadlag.tables(histories, t0, hours, h, big_move)
        usable = [f for f in pool if h <= f < hours - 1 - h]
        n, mb, ma, mbig = leadlag._sums(real, tab)
        row = {"onsets_with_markets": sum(1 for f in real if tab[0][f]), "pairs": n}
        if not n or not usable:
            out["horizons"][str(h)] = row
            continue
        rand_after, rand_before, rand_big = [], [], []
        for _ in range(draws):
            fake = [rng.choice(usable) for _ in real]
            rn, rb, ra, rbig = leadlag._sums(fake, tab)
            if rn:
                rand_after.append(ra)
                rand_before.append(rb)
                rand_big.append(rbig)
        base = _mean(rand_after)
        per = sorted(((tab[2][f] / tab[0][f], f) for f in set(real) if tab[0][f]), reverse=True)
        rest = [f for f in real if not per or f != per[0][1]]
        _n, _b, ma_rest, _big = leadlag._sums(rest, tab)
        row.update({
            "largest_onset": datetime.fromtimestamp(t0 + per[0][1] * HOUR, timezone.utc).date().isoformat() if per else None,
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


def fetch_missing(cfg, root=ROOT, fetch=fetch_text, now=None, log=print):
    """Daily closes for any gauge ticker the price folder lacks."""
    for t in tickers(cfg):
        if prices.load(t, root) is None:
            rep = prices.fetch_one(t, cfg["history_start"], root, fetch, now)
            log(("ok   " if rep["ok"] else "FAIL ") + rep["source"] + (f": {rep['items']} days" if rep["ok"] else f": {rep['error']}"))


def run(root=ROOT, fetch=fetch_text, now=None, log=print, markets_data=None):
    cfg = load_config(root)
    now = now or datetime.now(timezone.utc)
    fetch_missing(cfg, root, fetch, now, log)
    data = markets_data if markets_data is not None else leadlag.fetch_markets(root, fetch, now, log=log)
    since = datetime.fromisoformat(cfg["since"]).replace(tzinfo=timezone.utc).timestamp()
    t1 = now.timestamp()
    histories = [leadlag.hourly(m["history"], since) for m in data.values()]
    gauges = {}
    for g in cfg["gauges"]:
        rows = series(g, root)
        if not rows:
            gauges[g["id"]] = {"name": g["name"], "onsets": 0, "horizons": {}, "verdict": "no price history", "firings": []}
            continue
        fired, calendar = firings(rows, g["kind"], g["direction"], cfg["big_move_sd"], cfg["swing_days"], cfg["min_history_days"], cfg["quiet_days"])
        fired = [f for f in fired if f["date"] >= cfg["since"]]
        calendar = [d for d in calendar if d >= cfg["since"] and _close_ts(d, cfg["close_hour_utc"]) <= t1]
        res = measure(fired, calendar, histories, cfg["horizons"], since, t1, cfg["close_hour_utc"], cfg["random_draws"], cfg["big_move"])
        res["verdict"] = leadlag.verdict(res, cfg["alpha"], cfg["min_onsets"])
        res["name"], res["firings"], res["trading_days"] = g["name"], fired, len(calendar)
        gauges[g["id"]] = res
        log(f"{g['name']}: {len(fired)} firings, {res['verdict']}")
    result = {
        "run_at": now.replace(microsecond=0).isoformat(), "since": cfg["since"], "close_hour_utc": cfg["close_hour_utc"],
        "big_move_sd": cfg["big_move_sd"], "quiet_days": cfg["quiet_days"], "horizons": cfg["horizons"],
        "random_draws": cfg["random_draws"], "big_move": cfg["big_move"],
        "markets": sum(g is not None for g in histories),
        "note": "Moves are absolute changes in the Yes price of Polymarket strike and ceasefire markets, in probability points, "
                "from hourly prices, measured from the US close on the day the gauge fired. The baseline is random trading days from the same gauge's calendar.",
        "gauges": gauges,
    }
    out = Path(root) / "data" / "fear" / "result.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    return result


def load(root=ROOT):
    path = Path(root) / "data" / "fear" / "result.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None
