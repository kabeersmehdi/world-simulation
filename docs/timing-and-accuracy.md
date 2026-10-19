---
type: policy
title: Timing curves and market accuracy
status: active
generated:
  by: human-reviewed
  at: 2026-10-18
---

# Timing curves and market accuracy

## "If not, when?"
Polymarket lists the same question at several dates ("ceasefire holds through October 31", "through November 15" and so on). `worldsim/timing.py` reads a ladder from `config/ladders.json` and turns it into:

- the chance the event happens in each window between two dates
- the chance it has happened by each date
- the **median date**, where that chance crosses 50%, by straight-line interpolation
- the chance it still has not happened after the last date

A **survival** ladder ("still holds through d") is flipped so the event is the break. A **cumulative** ladder ("happens by d") is read as it is. Separate markets can disagree with each other, so the curve is smoothed to only move one way (pool-adjacent-violators) and the dashboard says when that happened.

## How good is the market?
`python -m worldsim backtest` scores every resolved yes/no Polymarket market found by the searches in `config/backtest.json` that traded at least the minimum volume. For each market it takes the price 30, 7 and 1 days before close and compares it with the outcome. A market counts as resolved when its final price is within 0.02 of 0 or 1 (`SETTLED`).

It reports the market's Brier score against two baselines: always guessing the historical yes share, and a coin flip (0.25). It also reports calibration bands: of the markets priced 70 to 80%, how many actually happened.

Limits, stated on the dashboard too:
- Ladder markets on one event move together, so the number of **events** is the fairer sample size, not the number of markets.
- The 1-day price can already reflect the news that settled the market. The 7- and 30-day prices are the fairer test.
- Search results decide the sample. They are not a random draw of all markets.

## Calibrated curves
Where the backtest shows a pattern (for example, ceasefire and strike markets priced 70 to 90% coming true more often than that), the timing view adds a **calibrated** column: each price is mapped to how often similar prices came true, then pulled back toward the raw price by `count / (count + 30)` (`SHRINK = 30`), so a thin band barely moves it. Calibration comes from 7-day prices, so it is weaker for dates months away. Treat it as a second opinion on the market, not a replacement.
