"""Daily closing prices for the event study, from Yahoo Finance's public chart endpoint."""

import json
import re
import urllib.parse
from datetime import date, datetime, timezone
from pathlib import Path

from . import ROOT
from .collectors.http import fetch_text

CHART_URL = "https://query1.finance.yahoo.com/v8/finance/chart/{ticker}?period1={start}&period2={end}&interval=1d"


def load_config(root=ROOT):
    return json.loads((Path(root) / "config" / "assets.json").read_text(encoding="utf-8"))


def _file(root, ticker):
    return Path(root) / "data" / "prices" / (re.sub(r"[^A-Za-z0-9]+", "_", ticker).strip("_") + ".json")


def parse_chart(text):
    """Yahoo chart JSON -> [(YYYY-MM-DD, close)] in the exchange's local dates, skipping empty days."""
    result = json.loads(text)["chart"]["result"][0]
    offset = result["meta"].get("gmtoffset", 0)
    closes = result["indicators"]["quote"][0]["close"]
    rows = {}
    for ts, close in zip(result.get("timestamp") or [], closes):
        if close is None:
            continue
        rows[datetime.fromtimestamp(ts + offset, tz=timezone.utc).date().isoformat()] = float(close)
    return sorted(rows.items())


def fetch_one(ticker, history_start, root=ROOT, fetch=fetch_text, now=None):
    """Fetch and save one ticker's daily closes since history_start. Returns a report row."""
    start = int(datetime.fromisoformat(history_start).replace(tzinfo=timezone.utc).timestamp())
    end = int((now or datetime.now(timezone.utc)).timestamp())
    try:
        rows = parse_chart(fetch(CHART_URL.format(ticker=urllib.parse.quote(ticker), start=start, end=end)))
        if len(rows) < 30:
            raise ValueError(f"only {len(rows)} days returned")
        path = _file(root, ticker)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"ticker": ticker, "source": "Yahoo Finance chart endpoint",
                                    "fetched_at": (now or datetime.now(timezone.utc)).replace(microsecond=0).isoformat(),
                                    "rows": rows}) + "\n")
        return {"source": f"prices:{ticker}", "ok": True, "items": len(rows), "flagged": 0}
    except Exception as exc:  # noqa: BLE001
        return {"source": f"prices:{ticker}", "ok": False, "error": f"{type(exc).__name__}: {exc}"}


def collect(root=ROOT, fetch=fetch_text, now=None):
    cfg = load_config(root)
    return [fetch_one(asset["ticker"], cfg["history_start"], root, fetch, now) for asset in cfg["assets"]]


def load(ticker, root=ROOT):
    path = _file(root, ticker)
    if not path.exists():
        return None
    return [(d, c) for d, c in json.loads(path.read_text())["rows"]]


def first_index_on_or_after(rows, day):
    for i, (d, _) in enumerate(rows):
        if d >= day:
            return i
    return None


def to_date(value):
    return value if isinstance(value, str) else date.isoformat(value)
