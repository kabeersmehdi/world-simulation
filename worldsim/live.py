"""Markets now: live quotes for the assets geopolitics moves, and a plain stress read.

Quotes come from a TradingView quote tool when one is set up in config/local.json
(it is run as a separate program; none of its code is copied here), otherwise from
Yahoo Finance's keyless chart endpoint. The stress read compares today with each
asset's past year, using the daily history from `python -m worldsim prices`.

Thresholds are mirrored in docs/markets-now.md and locked by a test. This is a
description of the market, not a trading signal.
"""

import json
import os
import statistics
import subprocess
import tempfile
import urllib.parse
from datetime import datetime, timezone
from pathlib import Path

from . import ROOT, prices
from .collectors.http import fetch_text

YAHOO_URL = "https://query1.finance.yahoo.com/v8/finance/chart/{ticker}?range=5d&interval=1d"
BIG_MOVE = 1.5        # today's move, in normal daily swings, that counts as big
VERY_BIG_MOVE = 3.0
HIGH_PERCENTILE = 80  # a level higher than this share of the past year counts as high
STRESS_LEVELS = [(3, "high stress"), (1, "some stress"), (0, "calm")]
YEAR = 252


def load_config(root=ROOT):
    return json.loads((Path(root) / "config" / "live.json").read_text(encoding="utf-8"))["assets"]


def local_settings(root=ROOT):
    """config/local.json (not committed) or WORLDSIM_TV_TOOL. Returns the tool folder and python, or None."""
    tool = os.environ.get("WORLDSIM_TV_TOOL")
    python = os.environ.get("WORLDSIM_TV_PYTHON")
    path = Path(root) / "config" / "local.json"
    if path.exists():
        cfg = json.loads(path.read_text(encoding="utf-8"))
        tool = tool or cfg.get("tradingview_tool")
        python = python or cfg.get("tradingview_python")
    if not tool:
        return None
    tool = Path(os.path.expanduser(tool))
    script = tool / "scripts" / "snapshot_quotes.py"
    if not script.exists():
        return None
    return {"tool": tool, "script": script, "python": python or "python3"}


def tradingview_watchlist(assets, tool):
    """A watchlist file in the TradingView tool's own format, built from config/live.json."""
    base = json.loads((tool / "config" / "watchlist.json").read_text(encoding="utf-8"))
    return {"timezone": base["timezone"], "session_anchor": "SPY", "history_plan": base["history_plan"],
            "symbols": [{"alias": a["alias"], "tv_symbol": a["tv_symbol"], "kind": a["kind"]} for a in assets],
            "internals": [], "optional_symbols": []}


def from_tradingview(assets, settings, run=subprocess.run):
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as fh:
        json.dump(tradingview_watchlist(assets, settings["tool"]), fh)
        wl = fh.name
    try:
        proc = run([settings["python"], str(settings["script"]), "--symbols-file", wl, "--wait-seconds", "10"],
                   capture_output=True, text=True, timeout=60, cwd=str(settings["tool"]))
    finally:
        os.unlink(wl)
    if proc.returncode != 0:
        raise RuntimeError(f"TradingView tool failed: {proc.stderr.strip()[-300:]}")
    data = json.loads(proc.stdout)
    by_symbol = data["quotes"]
    rows = []
    for a in assets:
        q = by_symbol.get(a["tv_symbol"])
        if not q or q.get("price") is None:
            continue
        rows.append({"alias": a["alias"], "price": q["price"], "change_pct": q.get("change_pct"),
                     "freshness": q.get("freshness"), "delay_minutes": q.get("feed_delay_minutes") or 0,
                     "quote_time": q.get("quote_time_et")})
    return rows, {"source": "TradingView (through the local quote tool)", "as_of": data.get("snapshot_time_et"),
                  "notes": data.get("data_quality", [])}


def from_yahoo(assets, fetch=fetch_text):
    rows = []
    for a in assets:
        try:
            meta = json.loads(fetch(YAHOO_URL.format(ticker=urllib.parse.quote(a["yahoo"]))))["chart"]["result"][0]["meta"]
        except Exception:  # noqa: BLE001 - one missing quote never stops the panel
            continue
        price, prev = meta.get("regularMarketPrice"), meta.get("chartPreviousClose") or meta.get("previousClose")
        if price is None:
            continue
        rows.append({"alias": a["alias"], "price": float(price),
                     "change_pct": round((price / prev - 1) * 100, 2) if prev else None,
                     "freshness": "DELAYED", "delay_minutes": 15, "quote_time": None})
    return rows, {"source": "Yahoo Finance (about 15 minutes delayed)", "as_of": None, "notes": []}


def snapshot(root=ROOT, now=None, fetch=fetch_text, run=subprocess.run):
    assets = load_config(root)
    settings = local_settings(root)
    rows, meta = [], None
    if settings:
        try:
            rows, meta = from_tradingview(assets, settings, run)
        except Exception as exc:  # noqa: BLE001 - fall back to Yahoo, and say so
            meta = {"source": "Yahoo Finance (TradingView tool failed)", "notes": [str(exc)[:200]]}
    if not rows:
        failed = meta is not None
        rows, fallback = from_yahoo(assets, fetch)
        meta = {**fallback, "source": meta["source"] if failed else fallback["source"],
                "notes": (meta or {}).get("notes", []) + fallback["notes"]}
    names = {a["alias"]: a for a in assets}
    for r in rows:
        r.update({"name": names[r["alias"]]["name"], "group": names[r["alias"]]["group"]})
    out = {"at": (now or datetime.now(timezone.utc)).replace(microsecond=0).isoformat(), **meta, "quotes": rows}
    path = Path(root) / "data" / "live" / "latest.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    return out


def load(root=ROOT):
    path = Path(root) / "data" / "live" / "latest.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None


def _daily(root, yahoo):
    rows = prices.load(yahoo, root)
    return rows[-(YEAR + 1):] if rows else None


def percentile(value, history):
    return round(100 * sum(1 for h in history if h < value) / len(history)) if history else None


def stress(snap, root=ROOT):
    """Words for each quote (normal day / big move) and an overall stress level."""
    if not snap:
        return None
    assets = {a["alias"]: a for a in load_config(root)}
    quotes = {q["alias"]: q for q in snap["quotes"]}
    rows, flags = [], []
    for alias, q in quotes.items():
        hist = _daily(root, assets[alias]["yahoo"])
        swing = None
        if hist and len(hist) > 30:
            moves = [(hist[i][1] / hist[i - 1][1] - 1) * 100 for i in range(1, len(hist))]
            swing = statistics.pstdev(moves)
        z = (q["change_pct"] / swing) if swing and q.get("change_pct") is not None else None
        size = None if z is None else ("very big move" if abs(z) >= VERY_BIG_MOVE else "big move" if abs(z) >= BIG_MOVE else "normal day")
        rows.append({**q, "normal_swing": round(swing, 2) if swing else None, "swings": round(z, 1) if z is not None else None, "size": size})
    by = {r["alias"]: r for r in rows}

    def big_up(alias):
        r = by.get(alias)
        return bool(r and r["swings"] is not None and r["swings"] >= BIG_MOVE)

    reads = []
    ovx = by.get("OVX")
    ovx_hist = _daily(root, "^OVX")
    if ovx and ovx_hist:
        pct = percentile(ovx["price"], [c for _, c in ovx_hist])
        reads.append({"what": "Oil options fear (OVX)", "value": f"{ovx['price']:.1f}", "detail": f"higher than {pct}% of the past year"})
        if pct is not None and pct >= HIGH_PERCENTILE:
            flags.append("oil options fear is high")
    b, w = by.get("BRENT"), by.get("WTI")
    bh, wh = _daily(root, "BZ=F"), _daily(root, "CL=F")
    if b and w and bh and wh:
        wmap = dict(wh)
        spreads = [c - wmap[d] for d, c in bh if d in wmap]
        now_spread = b["price"] - w["price"]
        pct = percentile(now_spread, spreads)
        reads.append({"what": "Brent minus WTI (seaborne oil premium)", "value": f"${now_spread:.2f}",
                      "detail": f"wider than {pct}% of the past year" if pct is not None else ""})
        if pct is not None and pct >= HIGH_PERCENTILE:
            flags.append("the seaborne oil premium is wide")
    if big_up("BRENT"):
        flags.append("oil rose a lot in the latest session")
    if sum(big_up(a) for a in ("ESLT", "LMT", "RTX", "ITA")) >= 2:
        flags.append("defense stocks rose a lot in the latest session")
    if big_up("USDILS"):
        flags.append("the shekel fell a lot in the latest session")
    level = next(name for floor, name in STRESS_LEVELS if len(flags) >= floor)
    return {"level": level, "flags": flags, "reads": reads, "quotes": rows, "calibrated": False}
