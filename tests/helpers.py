"""Shared test helpers. Every test that writes uses an isolated copy of the repo."""

import json
import shutil
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from worldsim import ROOT

FIXTURES = Path(__file__).parent / "fixtures"
NOW = datetime(2026, 10, 18, 21, 0, tzinfo=timezone.utc)
NOW_ISO = NOW.isoformat()


def fixture(name):
    return (FIXTURES / name).read_text(encoding="utf-8")


def isolated_root():
    """Copy schemas, config, knowledge and seed data to a temp dir. Never the live data folders."""
    tmp = Path(tempfile.mkdtemp(prefix="worldsim-test-"))
    for d in ["schemas", "config", "countries", "docs"]:
        shutil.copytree(ROOT / d, tmp / d)
    for d in ["evidence", "demo", "baserates", "scenarios", "polls", "timeline", "relationships", "markets"]:
        shutil.copytree(ROOT / "data" / d, tmp / "data" / d)
    (tmp / "data" / "forecasts").mkdir(parents=True)
    return tmp


def good_forecast(**overrides):
    fc = {
        "id": "fc-test", "question": "Will a test event happen by the deadline?",
        "resolution_criteria": "Yes if a named public source reports the test event.",
        "countries": ["israel"], "topic": "other",
        "created_at": "2026-10-01T00:00:00+00:00", "deadline": "2026-12-31T00:00:00+00:00",
        "status": "open", "illustrative": False, "reference_class": None,
        "history": [{"at": "2026-10-01T00:00:00+00:00", "probability": 0.4, "rationale": "Starting estimate from the base rate."}],
        "resolution": None,
    }
    fc.update(overrides)
    return fc


def write_json(path, obj):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(obj, ensure_ascii=False))
