"""Turn a reference class of past events into starting odds.

Sets starting odds; never calls exact dates. Anything under SMALL_SAMPLE
events carries a warning.
"""

import json
import statistics
from datetime import date
from pathlib import Path

from . import ROOT
from .contracts import validate

SMALL_SAMPLE = 20


def laplace(successes, trials):
    return (successes + 1) / (trials + 2)


def lag_days(event):
    if not event["responded"] or not event.get("response_date"):
        return None
    return (date.fromisoformat(event["response_date"]) - date.fromisoformat(event["trigger_date"])).days


def summarize(ref, within_days=(1, 7, 14, 30)):
    events = ref["events"]
    n = len(events)
    responded = [e for e in events if e["responded"]]
    lags = [d for d in (lag_days(e) for e in events) if d is not None]
    within = {}
    for days in within_days:
        k = sum(1 for d in lags if d <= days)
        within[str(days)] = laplace(k, n) if n else None
    return {
        "id": ref["id"],
        "description": ref["description"],
        "question_shape": ref["question_shape"],
        "inclusion_rule": ref["inclusion_rule"],
        "events": n,
        "verified_events": sum(1 for e in events if e["verified"]),
        "response_rate": laplace(len(responded), n) if n else None,
        "lag_days": {
            "median": statistics.median(lags) if lags else None,
            "min": min(lags) if lags else None,
            "max": max(lags) if lags else None,
        },
        "chance_within_days": within,
        "small_sample": n < SMALL_SAMPLE,
        "warning": (f"Only {n} events. Patterns this small are often noise. "
                    "Use as starting odds, then adjust with current evidence.") if n < SMALL_SAMPLE else None,
        "rows": [{**e, "lag_days": lag_days(e)} for e in events],
    }


def load_all(root=ROOT):
    out = []
    for path in sorted((Path(root) / "data" / "baserates").glob("*.json")):
        ref = validate(json.loads(path.read_text(encoding="utf-8")), "baserate", root)
        out.append(summarize(ref))
    return out
