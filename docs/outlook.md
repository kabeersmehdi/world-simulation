---
type: rubric
title: Plain-English outlook
status: active
generated:
  by: human-reviewed
  at: 2026-10-19
---

# Plain-English outlook

`worldsim/outlook.py` turns the forecasts and the Polymarket date ladders into the answers shown at the top of the Forecasts and Timeline tabs, and into `dashboard/brief.md` for the stocks report.

## Two numbers, always labeled
- **Our number:** this tool's forecast, the one that gets scored.
- **Polymarket:** the latest saved price from bettors. `collect` saves today's price for every open forecast's market.
- Within 5 points (`GAP_POINTS`) counts as the same. A bigger gap is where we disagree with the market, and where any edge would show up.

## Verdict words
| Chance | Verdict |
|---|---|
| 85% or more | Very likely |
| 65% or more | Likely |
| 55% or more | Leaning yes |
| 45% or more | Toss-up |
| 35% or more | Leaning no |
| 15% or more | Unlikely |
| under 15% | Very unlikely |

## Groups
Open forecasts are grouped by deadline: **This week** (7 days), **This month** (31 days), **Later**. Then **Past due**, **Decided** and **Withdrawn**.

## Most likely outcomes
- For rival outcomes in one `exclusive_group` (for example the next prime minister), the favorite by our number, then the next two.
- For each date ladder, the chance it holds or happens by the last date and the most likely date (the 50% point), using the calibrated curve.

## Stocks link
Military forecasts show how assets moved after past strikes, from the event study (robust patterns first). The brief lists the next 14 days, skips items under 10% (`BRIEF_MIN`), and keeps at most 8. None of it is a trading signal.
