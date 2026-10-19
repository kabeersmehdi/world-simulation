---
type: rubric
title: Markets now
status: active
generated:
  by: human-reviewed
  at: 2026-10-19
---

# Markets now

`python -m worldsim live` (and every `collect`) saves quotes for the assets geopolitics moves: oil, oil volatility, US and Israeli defense, tankers, ZIM, the shekel, Israeli stocks, gold, VIX and the S&P 500 (`config/live.json`).

## Where quotes come from
- **TradingView**, when `config/local.json` points to a local quote tool that has `scripts/snapshot_quotes.py`. The tool runs as a separate program; none of its code is copied into this repo. Its own freshness flags (live, closed, 15-minute delayed) are shown.
- **Yahoo Finance** otherwise, keyless and about 15 minutes delayed.

## The stress read
- **Size of move:** the latest session's move divided by the asset's normal daily swing over the past year. 1.5 swings or more is a big move (`BIG_MOVE`), 3.0 or more a very big move (`VERY_BIG_MOVE`).
- **Oil options fear:** the oil volatility index against its past year.
- **Seaborne oil premium:** Brent minus WTI against its past year. Brent is shipped by sea and carries Gulf risk; WTI is landlocked.
- A level higher than 80% of the past year counts as high (`HIGH_PERCENTILE`).
- **Flags:** oil options fear high, the seaborne premium wide, oil up a lot, two or more defense names up a lot, the shekel down a lot.
- **Level:** 0 flags is calm, 1 or 2 is some stress, 3 or more is high stress. Not calibrated yet.

Beside it, the panel shows what Polymarket prices on war risk (from the date ladders), so you can see whether the market's mood and the bettors' odds agree.

## Why no buy or sell calls
The accuracy backtest shows the crowd is hard to beat, and no forecast here has resolved yet. A trading rule built on an unproven number would put money behind noise. The panel describes the market; the Reactions tab shows how the same assets moved after past strikes. Decisions stay with the reader. Not investment advice.

## Speed
News moves prices within seconds; a laptop pulling feeds will not beat trading desks to a headline, and this tool does not try to. Its edge, if any, is judgment over days: Hebrew, Persian and Arabic sources, leading indicators, base rates and a scored record. `python -m worldsim watch --every 15` refreshes everything every 15 minutes, which is enough for that.
