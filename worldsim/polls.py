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
        if series.get("blocs"):
            add_blocs(series)
        out.append(series)
    return out


def add_blocs(series):
    """Sum bloc seats per poll, and average across polls with and without outliers named in the description."""
    for row in series["rows"]:
        row["bloc_totals"] = {name: sum(row["values"].get(p, 0) for p in parties)
                              for name, parties in series["blocs"].items()}
    names = list(series["blocs"])
    def avg(rows):
        return {n: round(sum(r["bloc_totals"][n] for r in rows) / len(rows), 1) for n in names} if rows else None
    leaders = {}
    for row in series["rows"]:
        top = max(row["values"], key=row["values"].get)
        leaders[top] = leaders.get(top, 0) + 1
    series["bloc_average"] = avg(series["rows"])
    series["bloc_average_without_channel_14"] = avg([r for r in series["rows"] if r.get("outlet") != "Channel 14"])
    series["largest_party_count"] = leaders
