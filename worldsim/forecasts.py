"""Forecast loading and guards.

Each guard is a small pure function that raises GuardError on a bad record.
Every guard has a red-team test in tests/test_forecasts.py.
"""

import json
from pathlib import Path

from . import ROOT
from .contracts import parse_datetime, validate

MIN_PROBABILITY = 0.01
MAX_PROBABILITY = 0.99


class GuardError(ValueError):
    pass


def guard_probability_bounds(fc):
    for h in fc["history"]:
        p = h["probability"]
        if not MIN_PROBABILITY <= p <= MAX_PROBABILITY:
            raise GuardError(f"{fc['id']}: probability {p} outside {MIN_PROBABILITY}-{MAX_PROBABILITY}; "
                             "0% and 100% are false certainty")


def guard_deadline_after_creation(fc):
    if parse_datetime(fc["deadline"]) <= parse_datetime(fc["created_at"]):
        raise GuardError(f"{fc['id']}: deadline must be after created_at")


def guard_history_order(fc):
    created = parse_datetime(fc["created_at"])
    times = [parse_datetime(h["at"]) for h in fc["history"]]
    if times[0] < created:
        raise GuardError(f"{fc['id']}: first update is dated before the forecast was created")
    if any(b < a for a, b in zip(times, times[1:])):
        raise GuardError(f"{fc['id']}: history entries are out of time order")


def guard_append_only(old, new):
    """The new version may only add history entries, never edit earlier ones."""
    if old is None:
        return
    fixed = ["question", "resolution_criteria", "created_at", "deadline"]
    for key in fixed:
        if old.get(key) != new.get(key):
            raise GuardError(f"{new['id']}: '{key}' changed after creation; open a new forecast instead")
    if new["history"][: len(old["history"])] != old["history"]:
        raise GuardError(f"{new['id']}: earlier history entries were edited or removed")


def guard_resolution(fc):
    res = fc.get("resolution")
    if fc["status"] == "resolved" and not res:
        raise GuardError(f"{fc['id']}: status is resolved but there is no resolution with a source")
    if fc["status"] == "open" and res:
        raise GuardError(f"{fc['id']}: has a resolution but status is still open")


def guard_no_illustrative_in_live(fc, live):
    if live and fc["illustrative"]:
        raise GuardError(f"{fc['id']}: illustrative forecasts belong in data/demo/, not data/forecasts/")
    if not live and not fc["illustrative"]:
        raise GuardError(f"{fc['id']}: demo forecasts must be marked illustrative")


def guard_exclusive_groups(fcs):
    """Outcomes that cannot both happen cannot add up to more than 100%."""
    groups = {}
    for fc in fcs:
        if fc.get("exclusive_group") and fc["status"] == "open":
            groups.setdefault(fc["exclusive_group"], []).append(fc)
    for name, members in groups.items():
        total = sum(current_probability(f) for f in members)
        if total > 1.0 + 1e-9:
            raise GuardError(f"group '{name}' adds up to {total:.0%}: {', '.join(f['id'] for f in members)}")


def check(fc, live, root=ROOT, previous=None):
    validate(fc, "forecast", root)
    guard_probability_bounds(fc)
    guard_deadline_after_creation(fc)
    guard_history_order(fc)
    guard_resolution(fc)
    guard_no_illustrative_in_live(fc, live)
    guard_append_only(previous, fc)
    return fc


def load_folder(folder, live, root=ROOT, previous=None):
    """Load and check every forecast file in a folder. previous maps id -> older version."""
    previous = previous or {}
    out = []
    for path in sorted(Path(folder).glob("*.json")):
        fc = json.loads(path.read_text(encoding="utf-8"))
        out.append(check(fc, live, root, previous.get(fc.get("id"))))
    return out


def load_all(root=ROOT, previous=None):
    root = Path(root)
    live = load_folder(root / "data" / "forecasts", True, root, previous)
    demo = load_folder(root / "data" / "demo", False, root, previous)
    guard_exclusive_groups(live)
    return live, demo


def current_probability(fc):
    return fc["history"][-1]["probability"]
