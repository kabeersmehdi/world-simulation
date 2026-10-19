"""Command line: python -m worldsim <command>

  collect        fetch every feed and market, save new items, then build
  build          rebuild dashboard/data.json from what is saved
  validate       check every forecast, evidence, poll and base-rate file
  score          print the scorecard
  live           live quotes for oil, defense, shipping and Israel, with a stress read
  watch          run collect every N minutes (default 15) until stopped
  prices         fetch daily prices and rerun the strike event study
  backtest       score resolved Polymarket markets on our topics (how good is the baseline?)
  new-forecast   write a forecast skeleton, optionally pre-filled from a Polymarket slug
"""

import argparse
import json
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from . import ROOT, backtest, build, eventstudy, live, prices, collectors, forecasts, markets, scoring, store, timing
from .contracts import ContractError


def cmd_collect(args):
    only = set(args.only) if args.only else None
    obs, report = collectors.run(ROOT, only=only)
    added = store.save(obs, ROOT)
    if not only:
        rows, mreport = markets.collect(ROOT)
        lrows, lreport = timing.collect(ROOT)
        markets.save(rows + lrows, ROOT)
        report += mreport + lreport
        try:
            snap = live.snapshot(ROOT)
            report.append({"source": f"markets now ({snap['source']})", "ok": True, "items": len(snap["quotes"]), "flagged": 0})
        except Exception as exc:  # noqa: BLE001
            report.append({"source": "markets now", "ok": False, "error": f"{type(exc).__name__}: {exc}"})
    failed = [r for r in report if not r["ok"]]
    for r in report:
        if r.get("skipped"):
            print(f"skip {r['source']}: {r['skipped']}")
            continue
        mark = "ok  " if r["ok"] else "FAIL"
        detail = f"{r['items']} items, {r['flagged']} flagged" if r["ok"] else r["error"]
        if r.get("via"):
            detail += f" via {r['via']}"
        print(f"{mark} {r['source']}: {detail}")
    print(f"\n{added} new observations saved, {len(failed)} source(s) failed.")
    build.build(ROOT)
    print("dashboard/data.json rebuilt.")
    return 0


def cmd_build(args):
    data = build.build(ROOT)
    print(f"Built dashboard/data.json: watch level {data['watch']['level']}, "
          f"{data['counts']['observations_10d']} observations, {data['counts']['live_forecasts']} live forecasts.")
    return 0


def cmd_validate(args):
    try:
        live, demo = forecasts.load_all(ROOT)
        build.build(ROOT, out_path=Path(args.out) if args.out else None)
    except (ContractError, forecasts.GuardError, ValueError) as exc:
        print(f"FAIL: {exc}")
        return 1
    print(f"ok: {len(live)} live and {len(demo)} demo forecasts, all data files pass their contracts.")
    return 0


def cmd_score(args):
    live, _ = forecasts.load_all(ROOT)
    card = scoring.scorecard(live)
    print(json.dumps({k: v for k, v in card.items() if k != "rows"}, indent=2))
    if not card["enough_data"]:
        print(f"\nOnly {card['resolved']} resolved. No claim of an edge until {card['min_resolved_for_claims']}.")
    return 0


def cmd_backtest(args):
    print("Scoring resolved Polymarket markets (a few minutes)...")
    result = backtest.run(ROOT)
    for s in result["summary"]:
        print(f"\n{s['label']}: {s['markets']} markets across {s['events']} events")
        for h, v in s["horizons"].items():
            if v["n"]:
                print(f"  {h:>2} days before close: n={v['n']}, market Brier {v['market_brier']:.3f}, "
                      f"base rate {v['base_rate_brier']:.3f}, coin flip 0.250, right side {v['hit_rate']:.0%}")
    build.build(ROOT)
    print("\nSaved data/backtests/polymarket-geopolitics.json and rebuilt the dashboard.")
    return 0


def cmd_live(args):
    snap = live.snapshot(ROOT)
    s = live.stress(snap, ROOT)
    print(f"Markets now from {snap['source']}: {s['level']}" + (f" ({'; '.join(s['flags'])})" if s["flags"] else ""))
    for r in s["reads"]:
        print(f"  {r['what']}: {r['value']}, {r['detail']}")
    for q in s["quotes"]:
        move = "n/a" if q.get("change_pct") is None else f"{q['change_pct']:+.2f}%"
        print(f"  {q['name']:40} {q['price']:>10,.2f}  {move:>8}  {q['size'] or ''}")
    build.build(ROOT)
    return 0


def cmd_watch(args):
    import time
    print(f"Collecting every {args.every} minutes. Ctrl+C to stop.")
    while True:
        try:
            cmd_collect(argparse.Namespace(only=None))
        except Exception as exc:  # noqa: BLE001 - keep the loop alive, show the error
            print(f"collect failed: {exc}")
        try:
            time.sleep(args.every * 60)
        except KeyboardInterrupt:
            return 0


def cmd_prices(args):
    for r in prices.collect(ROOT):
        if not r["ok"]:
            print(f"FAIL {r['source']}: {r['error']}")
    result = eventstudy.run(ROOT)
    print(f"Event study: {len(result['events'])} events x {len(result['assets'])} assets.")
    for a in result["assets"]:
        hits = [f"day {k} {s['mean']:+.1f}%" + ("" if s["holds_without_largest"] else " (one event carries it)")
                for k, s in a["summary"].items() if s["unusual"]]
        if hits:
            print(f"  {a['name']}: " + ", ".join(hits))
    build.build(ROOT)
    print("Saved data/eventstudy/strike-reactions.json and rebuilt the dashboard.")
    return 0


def cmd_new_forecast(args):
    now = datetime.now(timezone.utc).replace(microsecond=0)
    question, deadline, market, bench = args.question, None, None, None
    if args.market:
        entry = next((m for m in markets.load_watchlist(ROOT) if m["slug"] == args.market),
                     {"slug": args.market, "label": args.market, "outcome_index": 0})
        snap = markets.snapshot(entry, now.isoformat())
        question = question or snap["question"]
        if snap["end_date"]:
            deadline = f"{snap['end_date']}T00:00:00+00:00"
        market = {"source": "polymarket", "slug": args.market, "outcome_index": entry.get("outcome_index", 0)}
        bench = snap["probability"]
    if not question:
        print("Give --question or --market.")
        return 1
    slug = re.sub(r"[^a-z0-9]+", "-", question.lower()).strip("-")[:50]
    fc = {
        "id": f"fc-{slug}", "question": question,
        "resolution_criteria": "WRITE THIS: the exact public fact that makes this resolve yes.",
        "countries": ["israel"], "topic": "other",
        "created_at": now.isoformat(), "deadline": deadline or (now + timedelta(days=90)).isoformat(),
        "status": "open", "illustrative": False,
        "reference_class": None, "market": market,
        "indicators_to_watch": [], "raise_if": [], "lower_if": [],
        "history": [{"at": now.isoformat(), "probability": -1, "rationale": "WRITE THIS: why this number.",
                     "evidence_ids": [], "benchmark_probability": bench}],
        "resolution": None,
    }
    path = ROOT / "data" / "forecasts" / f"{fc['id']}.json"
    if path.exists():
        print(f"{path} already exists.")
        return 1
    path.write_text(json.dumps(fc, ensure_ascii=False, indent=2) + "\n")
    print(f"Wrote {path.relative_to(ROOT)}. Market says {bench}. Fill in your probability, "
          "resolution rule, countries and topic, then run: python -m worldsim validate")
    return 0


def main(argv=None):
    p = argparse.ArgumentParser(prog="worldsim", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("collect")
    c.add_argument("--only", nargs="*", help="source ids from config/sources.json")
    sub.add_parser("build")
    v = sub.add_parser("validate")
    v.add_argument("--out", help="write the test build here instead of dashboard/data.json")
    sub.add_parser("score")
    sub.add_parser("backtest")
    sub.add_parser("prices")
    sub.add_parser("live")
    w = sub.add_parser("watch")
    w.add_argument("--every", type=int, default=15, help="minutes between runs (default 15)")
    n = sub.add_parser("new-forecast")
    n.add_argument("--question")
    n.add_argument("--market", help="Polymarket slug to pre-fill question, deadline and market price")
    args = p.parse_args(argv)
    return {"collect": cmd_collect, "build": cmd_build, "validate": cmd_validate,
            "score": cmd_score, "backtest": cmd_backtest, "prices": cmd_prices, "live": cmd_live, "watch": cmd_watch, "new-forecast": cmd_new_forecast}[args.cmd](args)


if __name__ == "__main__":
    sys.exit(main())
