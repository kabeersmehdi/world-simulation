"""The plain-English layer: what is most likely, ours versus Polymarket, what is coming up,
and which stocks moved after similar events before.

Verdict words and time groups are mirrored in docs/outlook.md and locked by a test.
"""

import json
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from . import ROOT, forecasts as F, markets
from .contracts import parse_datetime

# (lowest probability, verdict), checked from the top.
VERDICTS = [(0.85, "Very likely"), (0.65, "Likely"), (0.55, "Leaning yes"),
            (0.45, "Toss-up"), (0.35, "Leaning no"), (0.15, "Unlikely"), (0.0, "Very unlikely")]
GAP_POINTS = 5  # we only call it a disagreement with the market at 5 points or more
GROUPS = [(7, "This week"), (31, "This month"), (None, "Later")]
STOCK_TOPICS = {"military"}
BRIEF_MIN = 0.10   # the stocks brief skips forecasts below this chance
BRIEF_ITEMS = 8


def verdict(p):
    for floor, word in VERDICTS:
        if p >= floor:
            return word
    return VERDICTS[-1][1]


def gap_words(ours, market):
    if market is None:
        return "No market"
    pts = round((ours - market) * 100)
    if abs(pts) < GAP_POINTS:
        return "Same"
    return f"We're {abs(pts)} pts {'higher' if pts > 0 else 'lower'}"


def group_for(deadline, today):
    days = (deadline - today).days
    for limit, name in GROUPS:
        if limit is None or days <= limit:
            return name
    return GROUPS[-1][1]


def stock_moves(reactions, limit=5):
    """Short lines on how assets moved after past strikes, robust patterns first."""
    if not reactions:
        return []
    lines = []
    for a in reactions["assets"]:
        best = None
        for k in ("1", "5"):
            s = a["summary"].get(k) or {}
            if s.get("unusual") and (best is None or (s["holds_without_largest"] and not best[1]["holds_without_largest"])):
                best = (k, s)
        if best:
            k, s = best
            vs = " vs the S&P" if s["measure"] == "vs SPY" else ""
            lines.append({"ticker": a["ticker"], "name": a["name"], "days": int(k), "mean": s["mean"],
                          "holds": s["holds_without_largest"],
                          "text": f"{a['name']} {s['mean']:+.1f}%{vs} after {k} trading day{'s' if k != '1' else ''}"
                                  + ("" if s["holds_without_largest"] else " (mostly one event)")})
    lines.sort(key=lambda l: (not l["holds"], -abs(l["mean"])))
    return lines[:limit]


def forecast_rows(live, prices, reactions, today):
    moves = stock_moves(reactions)
    rows = []
    for fc in live:
        ours = F.current_probability(fc)
        slug = (fc.get("market") or {}).get("slug")
        market = prices.get(slug, (None, None))[0] if slug else None
        deadline = parse_datetime(fc["deadline"]).date()
        status = fc["status"]
        group = ("Decided" if status == "resolved" else "Withdrawn" if status == "annulled"
                 else "Past due" if deadline < today else group_for(deadline, today))
        rows.append({
            "id": fc["id"], "question": fc["question"], "topic": fc["topic"], "deadline": deadline.isoformat(),
            "group": group, "ours": ours, "market": market, "verdict": verdict(ours),
            "market_verdict": verdict(market) if market is not None else None,
            "gap": gap_words(ours, market), "gap_points": round((ours - market) * 100) if market is not None else None,
            "rule": fc["resolution_criteria"], "why": fc["history"][-1]["rationale"],
            "updates": len(fc["history"]), "outcome": (fc.get("resolution") or {}).get("outcome"),
            "withdrawn_reason": fc.get("annulled_reason"),
            "market_url": f"https://polymarket.com/market/{slug}" if slug else None,
            "stock_moves": moves if fc["topic"] in STOCK_TOPICS else [],
        })
    order = {name: i for i, (_, name) in enumerate(GROUPS)} | {"Past due": -1, "Decided": 10, "Withdrawn": 11}
    rows.sort(key=lambda r: (order.get(r["group"], 5), r["deadline"]))
    return rows


GROUP_TITLES = {"il-next-pm-2026": "Next Israeli prime minister"}


def headlines(live, rows, timing):
    """The few big answers: the favorite in each group of rival outcomes, and each 'when' curve."""
    by_id = {r["id"]: r for r in rows}
    out, groups = [], {}
    for fc in live:
        g = fc.get("exclusive_group")
        if g and fc["status"] == "open" and fc["id"] in by_id:
            groups.setdefault(g, []).append(by_id[fc["id"]])
    for g, members in groups.items():
        members.sort(key=lambda r: -r["ours"])
        top = members[0]
        rest = ", ".join(f"{m['question'].split(' be the ')[0].replace('Will ', '')} {round(m['ours'] * 100)}%" for m in members[1:3])
        name = top["question"].split(" be the ")[0].replace("Will ", "")
        out.append({"title": GROUP_TITLES.get(g, g), "answer": f"{name}, {round(top['ours'] * 100)}%",
                    "detail": f"then {rest}" + (f" · Polymarket has {name} at {round(top['market'] * 100)}%" if top["market"] is not None else "")})
    for c in timing or []:
        cal = c.get("calibrated") or {}
        md = cal.get("median_date") or c.get("median_date")
        last = c["rows"][-1]["to"] if c["rows"] else None
        if not last:
            continue
        if c["kind"] == "survival":
            hold = cal.get("after_last", c["after_last"])
            answer = f"{round(hold * 100)}% it holds through {fmt(last)}"
            detail = f"most likely breaks around {fmt(md)}" if md else f"more likely than not to hold past {fmt(last)}"
        else:
            happened = 1 - cal.get("after_last", c["after_last"])
            answer = f"{round(happened * 100)}% by {fmt(last)}"
            detail = f"most likely around {fmt(md)}" if md else f"more likely after {fmt(last)}"
        out.append({"title": c["title"], "answer": answer, "detail": detail + " · from the Polymarket date ladder, adjusted for its track record"})
    return out


def coming_up(rows, timing, evidence, today, days=90):
    """Dated items ahead: scheduled events, forecast deadlines, and ceasefire break dates."""
    end = today + timedelta(days=days)
    items = []
    for ev in evidence:
        d = ev.get("event_date")
        if d and today.isoformat() <= d <= end.isoformat():
            items.append({"date": d, "kind": "scheduled", "title": ev["claim"], "likely": None, "detail": None})
    for r in rows:
        if r["group"] in ("This week", "This month", "Later") and r["deadline"] <= end.isoformat():
            items.append({"date": r["deadline"], "kind": "forecast", "title": r["question"], "p": r["ours"],
                          "likely": f"{r['verdict']} ({round(r['ours'] * 100)}%)",
                          "detail": f"Polymarket {round(r['market'] * 100)}%" if r["market"] is not None else None})
    for c in timing or []:
        cal = c.get("calibrated") or {}
        md = cal.get("median_date") or c.get("median_date")
        if md and md <= end.isoformat():
            event = "breaks" if c["kind"] == "survival" else "happens"
            items.append({"date": md, "kind": "most likely date", "title": f"{c['title']}: most likely {event} around this date",
                          "likely": "50/50 point", "detail": f"from the Polymarket date ladder ({len(c['rows'])} dates)"})
    items.sort(key=lambda i: i["date"])
    return items


def build(live, timing, reactions, evidence, root=ROOT, now=None):
    now = now or datetime.now(timezone.utc)
    today = now.date()
    rows = forecast_rows(live, markets.latest_prices(root, now=now), reactions, today)
    return {"forecasts": rows, "headlines": headlines(live, rows, timing), "coming_up": coming_up(rows, timing, evidence, today),
            "stock_moves": stock_moves(reactions, limit=8), "as_of": now.replace(microsecond=0).isoformat()}


def fmt(d):
    y, m, dd = d.split("-")
    return f"{m}/{dd}/{y}"


def brief_markdown(outlook, days=14):
    """A short geopolitics section for the stocks report: next two weeks, our number vs the market, stock links."""
    today = date.fromisoformat(outlook["as_of"][:10])
    end = (today + timedelta(days=days)).isoformat()
    lines = ["---", "type: brief", "title: Geopolitics brief for the stocks report", "generated:",
             "  by: worldsim/outlook.py", f"  at: {outlook['as_of'][:10]}", f"stale_after: {(today + timedelta(days=1)).isoformat()}", "---", "",
             f"## Geopolitics: next {days} days", "",
             f"_From world-simulation, {fmt(outlook['as_of'][:10])}. Ours = this tool's forecast. Polymarket = bettors' price._", "",
             "**Most likely:**"]
    lines += [f"- {h['title']}: **{h['answer']}** · {h['detail']}" for h in outlook.get("headlines", [])]
    lines += ["", "**Dated, next two weeks:**"]
    window = [i for i in outlook["coming_up"] if i["date"] <= end]
    soon = [i for i in window if i.get("p") is None or i["p"] >= BRIEF_MIN][:BRIEF_ITEMS]
    hidden = len(window) - len(soon)
    if not soon:
        lines.append("- Nothing dated in the next two weeks.")
    for i in soon:
        extra = f" · {i['likely']}" if i["likely"] else ""
        extra += f" · {i['detail']}" if i["detail"] else ""
        lines.append(f"- **{fmt(i['date'])}** {i['title']}{extra}")
    if hidden:
        lines.append(f"- _{hidden} more items under {round(BRIEF_MIN * 100)}% or past the first {BRIEF_ITEMS} are on the dashboard._")
    gaps = [r for r in outlook["forecasts"] if r["gap_points"] is not None and abs(r["gap_points"]) >= GAP_POINTS
            and r["group"] in ("This week", "This month", "Later")]
    lines += ["", "**Where we disagree with the market:** " + ("; ".join(f"{r['question']} ({r['gap']})" for r in gaps[:5]) if gaps else "nowhere yet")]
    if outlook["stock_moves"]:
        lines += ["", "**If a strike happens, past reactions** (average of past strikes, not a signal):"]
        lines += [f"- {m['text']}" for m in outlook["stock_moves"][:5]]
    return "\n".join(lines) + "\n"


def write_brief(outlook, root=ROOT):
    folder = Path(root) / "dashboard"
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "brief.md").write_text(brief_markdown(outlook), encoding="utf-8")
    (folder / "brief.json").write_text(json.dumps(outlook, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
