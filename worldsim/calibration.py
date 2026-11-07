"""Learn from the backtest how far the crowd's price sits from the truth, by horizon.

The first method was one fixed rule: move prices under 10% or over 90% a third
of the way to the edge. The backtest says the gap depends on how far away the
close is. At 30 and 7 days the crowd overprices long shots a little; in the last
two days it does not. So the map is fitted per horizon on the resolved markets in
data/backtests/, as a staircase that can only rise (pool-adjacent-violators),
shrunk toward the raw price where the backtest is thin, and switched off close to
the deadline.

It is checked the only honest way: fit on markets that closed before CUTOFF,
score the ones that closed after. The result is saved beside the map, and the
dashboard shows it. Expect a small gain, about a thousandth of a Brier point.
That is not an edge; it is the crowd's price with one known bias taken out.
Constants are mirrored in docs/forecasting-policy.md and locked by a test.
"""

import json
from datetime import datetime, timezone
from pathlib import Path

from . import ROOT
from .scoring import brier

HORIZON_FOR_DAYS = ((14, "30"), (2, "7"))  # days to the deadline at or above the first number use that backtest horizon
MAX_DAYS = 90        # beyond this the backtest has no price to learn from, so the raw price stands
SHRINK = 30          # markets in a step at which the fitted rate gets half the weight
CUTOFF = "2026-08-01"  # fit on markets closed before this, test on the rest
FLOOR, CEIL = 0.01, 0.99


def horizon_for(days_to_deadline):
    """Which backtest horizon applies. None inside the last two days (no bias found there) and past MAX_DAYS (never tested)."""
    if days_to_deadline > MAX_DAYS:
        return None
    for floor, horizon in HORIZON_FOR_DAYS:
        if days_to_deadline >= floor:
            return horizon
    return None


def pav(points):
    """Pool adjacent violators: the rising staircase that best fits (price, outcome) pairs.

    Returns steps as (low price, high price, share that happened, markets in the step).
    """
    grouped = {}
    for x, y in points:  # markets at the same price pool first, so a crowded price is one well-sized step
        g = grouped.setdefault(x, [0.0, 0])
        g[0] += 1.0 if y else 0.0
        g[1] += 1
    blocks = [[x, yes, n, x, x] for x, (yes, n) in sorted(grouped.items())]
    out = []
    for blk in blocks:
        out.append(blk)
        while len(out) > 1 and out[-2][1] / out[-2][2] > out[-1][1] / out[-1][2]:
            right, left = out.pop(), out.pop()
            out.append([None, left[1] + right[1], left[2] + right[2], left[3], right[4]])
    return [(b[3], b[4], b[1] / b[2], b[2]) for b in out]


def fit(rows, horizons=("30", "7", "1")):
    """One staircase per horizon from backtest rows (each has p30, p7, p1 and outcome)."""
    model = {}
    for h in horizons:
        pts = [(r[f"p{h}"], r["outcome"]) for r in rows if r.get(f"p{h}") is not None and r.get("outcome") is not None]
        model[h] = {"n": len(pts), "steps": [list(s) for s in pav(pts)] if len(pts) >= 10 else []}
    return model


def adjust(price, days_to_deadline, model):
    """The crowd's price with the horizon's known bias taken out. Unchanged when there is nothing to apply."""
    horizon = horizon_for(days_to_deadline)
    steps = (model or {}).get(horizon, {}).get("steps") if horizon else None
    if not steps:
        return price
    step = next((s for s in steps if price <= s[1]), steps[-1])
    lo, hi, rate, n = step
    weight = n / (n + SHRINK)
    return round(min(max(price + weight * (rate - price), FLOOR), CEIL), 4)


def _days_for(horizon):
    return int(horizon)


def check(rows, cutoff=CUTOFF):
    """Fit before the cutoff, score after it. Says per horizon whether the map helped."""
    train = [r for r in rows if r.get("closed") and r["closed"] < cutoff]
    test = [r for r in rows if r.get("closed") and r["closed"] >= cutoff]
    model = fit(train)
    out = {"cutoff": cutoff, "train_markets": len(train), "test_markets": len(test), "horizons": {}}
    for h in ("30", "7", "1"):
        rs = [r for r in test if r.get(f"p{h}") is not None and r.get("outcome") is not None]
        if not rs:
            out["horizons"][h] = None
            continue
        raw = sum(brier(r[f"p{h}"], r["outcome"]) for r in rs) / len(rs)
        adj = sum(brier(adjust(r[f"p{h}"], _days_for(h), model), r["outcome"]) for r in rs) / len(rs)
        out["horizons"][h] = {"n": len(rs), "raw_brier": round(raw, 4), "adjusted_brier": round(adj, 4),
                              "gain": round(raw - adj, 4), "helps": adj < raw}
    return out


def build(root=ROOT, now=None):
    """Fit on the saved backtest and save data/backtests/calibration.json. No network."""
    root = Path(root)
    src = root / "data" / "backtests" / "polymarket-geopolitics.json"
    if not src.exists():
        return None
    rows = [r for r in json.loads(src.read_text(encoding="utf-8"))["rows"] if r.get("outcome") is not None]
    out = {
        "fitted_at": (now or datetime.now(timezone.utc)).replace(microsecond=0).isoformat(),
        "note": "How far the crowd's price sits from the truth, by horizon. Fitted on every resolved market in the backtest; "
                "the check fits on markets closed before the cutoff and scores the rest.",
        "markets": len(rows), "shrink": SHRINK, "horizon_for_days": [list(x) for x in HORIZON_FOR_DAYS], "max_days": MAX_DAYS,
        "horizons": fit(rows), "check": check(rows),
    }
    path = root / "data" / "backtests" / "calibration.json"
    path.write_text(json.dumps(out, indent=1) + "\n", encoding="utf-8")
    return out


def load(root=ROOT):
    path = Path(root) / "data" / "backtests" / "calibration.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None


def table(model, horizon, prices=(0.02, 0.05, 0.1, 0.2, 0.3, 0.5, 0.7, 0.9, 0.95)):
    """A few sample prices and what the map turns them into, for the dashboard."""
    days = _days_for(horizon)
    return [{"price": p, "adjusted": adjust(p, days, model)} for p in prices]
