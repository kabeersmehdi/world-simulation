"""Decision-maker cards: who wants what, what stops them, and how you would know they are moving.

A card is a checklist, not a model. An independent forecast names the players it
rests on, says what each one does in the scenario, and gets scored like any other.
That is how we find out whether reasoning about the players beats copying the crowd.
"""

import json
from pathlib import Path

from . import ROOT
from .contracts import validate

MARKED = ("(reported", "(inferred", "(stated", "(open research")
ID_PREFIXES = ("ev-", "tl-", "fc-", "br-", "rel-", "config/")


def load_all(root=ROOT):
    out = []
    for path in sorted((Path(root) / "data" / "actors").glob("*.json")):
        out.append(validate(json.loads(path.read_text(encoding="utf-8")), "actor", root))
    return out


def ids(root=ROOT):
    return {a["id"] for a in load_all(root)}


def unmarked_lines(card):
    """Lines in wants, fears, constraints or red lines that cite nothing and carry no (reported), (inferred) or (stated) mark."""
    bad = []
    for key in ("wants", "fears", "constraints", "red_lines"):
        for line in card.get(key, []):
            if not any(m in line for m in MARKED) and not any(pfx in line for pfx in ID_PREFIXES):
                bad.append(f"{card['id']}.{key}: {line[:60]}")
    return bad
