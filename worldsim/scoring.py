"""Brier scoring, calibration bands and baseline comparison."""

from .contracts import parse_datetime

MIN_RESOLVED_FOR_CLAIMS = 20


def brier(probability, outcome):
    if not 0 <= probability <= 1:
        raise ValueError(f"probability {probability} outside 0-1")
    return (probability - (1.0 if outcome else 0.0)) ** 2


def scored_probability(fc):
    """The last probability made on or before the deadline."""
    deadline = parse_datetime(fc["deadline"])
    eligible = [h for h in fc["history"] if parse_datetime(h["at"]) <= deadline]
    return eligible[-1]["probability"] if eligible else None


def _mean(values):
    return sum(values) / len(values) if values else None


def scorecard(forecasts):
    resolved = [f for f in forecasts if f["status"] == "resolved" and f.get("resolution")]
    rows = []
    for f in resolved:
        p = scored_probability(f)
        if p is None:
            continue
        outcome = f["resolution"]["outcome"]
        base = (f.get("reference_class") or {}).get("base_rate")
        market = f["history"][0].get("benchmark_probability")
        rows.append({
            "id": f["id"],
            "topic": f["topic"],
            "probability": p,
            "outcome": outcome,
            "brier": brier(p, outcome),
            "base_rate_brier": brier(base, outcome) if base is not None else None,
            "market_brier": brier(market, outcome) if market is not None else None,
        })

    bands = []
    for i in range(10):
        lo, hi = i / 10, (i + 1) / 10
        in_band = [r for r in rows if lo <= r["probability"] < hi or (i == 9 and r["probability"] == 1)]
        bands.append({
            "band": f"{int(lo * 100)}-{int(hi * 100)}%",
            "count": len(in_band),
            "mean_forecast": _mean([r["probability"] for r in in_band]),
            "observed_rate": _mean([1.0 if r["outcome"] else 0.0 for r in in_band]),
        })

    by_topic = {}
    for r in rows:
        by_topic.setdefault(r["topic"], []).append(r["brier"])

    with_base = [r for r in rows if r["base_rate_brier"] is not None]
    with_market = [r for r in rows if r["market_brier"] is not None]
    return {
        "resolved": len(rows),
        "open": sum(1 for f in forecasts if f["status"] == "open"),
        "enough_data": len(rows) >= MIN_RESOLVED_FOR_CLAIMS,
        "min_resolved_for_claims": MIN_RESOLVED_FOR_CLAIMS,
        "mean_brier": _mean([r["brier"] for r in rows]),
        "vs_base_rate": {
            "n": len(with_base),
            "ours": _mean([r["brier"] for r in with_base]),
            "baseline": _mean([r["base_rate_brier"] for r in with_base]),
        },
        "vs_market": {
            "n": len(with_market),
            "ours": _mean([r["brier"] for r in with_market]),
            "baseline": _mean([r["market_brier"] for r in with_market]),
        },
        "calibration": bands,
        "by_topic": {t: {"n": len(v), "mean_brier": _mean(v)} for t, v in sorted(by_topic.items())},
        "rows": rows,
    }


def overdue(forecasts, now):
    return [f["id"] for f in forecasts if f["status"] == "open" and parse_datetime(f["deadline"]) < now]
