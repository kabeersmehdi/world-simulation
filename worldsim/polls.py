"""Leader approval and preference polls, each row sourced."""

import json
from pathlib import Path

from . import ROOT
from .contracts import validate


def load_all(root=ROOT):
    out = []
    for path in sorted((Path(root) / "data" / "polls").glob("*.json")):
        series = validate(json.loads(path.read_text(encoding="utf-8")), "poll", root)
        series["rows"].sort(key=lambda r: r["fieldwork_end"], reverse=True)
        series["latest"] = series["rows"][0] if series["rows"] else None
        out.append(series)
    return out
