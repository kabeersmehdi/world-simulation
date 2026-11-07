---
type: policy
title: Forecasting policy
status: active
generated:
  by: human-reviewed
  at: 2026-10-18
---

# Forecasting policy

## Every forecast must have
- A precise question and a resolution rule anyone could apply
- A deadline after the creation date
- A probability between 1% and 99% (0% and 100% are rejected as false certainty)
- A rationale for every probability update
- Where possible: a reference class with a base rate, and the market price on the same day

## Guards (enforced in `worldsim/forecasts.py`)
| Guard | Rejects |
|---|---|
| `guard_probability_bounds` | Any probability below 0.01 or above 0.99 |
| `guard_deadline_after_creation` | A deadline on or before the creation date |
| `guard_history_order` | Updates out of time order, or dated before creation |
| `guard_append_only` | Any change to an earlier history entry (no hindsight edits) |
| `guard_resolution` | A resolved forecast with no outcome source, an open one with a resolution, or an annulled one with no `annulled_reason` |
| `guard_no_illustrative_in_live` | An illustrative forecast saved in `data/forecasts/` |
| `guard_exclusive_groups` | Open forecasts in one `exclusive_group` (for example rival candidates) adding up to more than 100% |

Each guard has a red-team test that feeds it a bad record and checks it is rejected.

## Withdrawing a forecast
A forecast is never deleted or rewritten. To withdraw one, set `status` to `annulled` and say why in `annulled_reason`. It stays in the record and is never scored. Avoid questions priced above 95% or below 5%: they score well whatever you do, so they teach nothing.

## Scoring
- Brier score on resolved yes/no forecasts, using the last probability made before the deadline.
- Compared against two baselines: the reference-class base rate, and the market price logged with the first update.
- Calibration shown in ten probability bands.
- No claim of an edge until at least 20 forecasts have resolved (`MIN_RESOLVED_FOR_CLAIMS`). Below that the dashboard says "not enough data".

## The method, since 11/07/2026
Every forecast's number comes from one of two views, written on the history entry as `view`:

**Market view.** The crowd's price with the horizon's known bias taken out. `worldsim/calibration.py` fits one map per horizon on the resolved markets in the backtest: a staircase that can only rise (pool-adjacent-violators), shrunk toward the raw price where the backtest is thin (`SHRINK = 30`: a step with 30 markets gets half the weight). Which map applies depends on how far the deadline is:

| Days to the deadline | Map |
|---|---|
| more than `MAX_DAYS = 90` | none: the backtest has no price that far out, the raw price stands |
| 14 days or more | the 30-day map |
| 2 days or more | the 7-day map |
| under 2 days | none: the backtest found no bias in the last two days |

The map is checked the only honest way: fit on markets closed before `CUTOFF = 2026-08-01`, score the rest. `python -m worldsim backtest --fit` refits it from the saved backtest and prints the check. On 11/07/2026: 30 days out 0.0592 to 0.0581, 7 days out 0.0655 to 0.0646, 1 day out no change. About a thousandth of a Brier point. That is the crowd's price with one known bias removed, not an edge.

**Independent view.** Our own number, which must name the players it rests on (`players`: a card id from `data/actors/` and what that player does in the scenario) and say why in the rationale. `guard_independent_view` rejects an independent entry with no known player. See [the player cards](players.md). The scorecard splits resolved forecasts by view, so the record shows whether reasoning about the players beats copying the crowd.

The old fixed rule (prices under 10% or over 90% moved 30% closer to the edge, whatever the horizon) is retired. On the 1,422 backtest markets it gained nothing in the last day before close and about 0.0004 a week out.

## The sprint, scored (10/19 to 11/05/2026)
Eighteen forecasts on fast-resolving markets plus the open election set: 21 resolved by 11/05/2026. All of them copied the market price with the old fixed rule; none carried a news view. The fair comparison is against the market price logged at the same time as the scored number:

| | Ours | Market, same time | n |
|---|---|---|---|
| All resolved | 0.0697 | 0.0701 | 21 |
| Sprint only | 0.0550 | 0.0555 | 17 |
| Not about the election | 0.0094 | 0.0099 | 13 |

Lower is better. The gap is a few ten-thousandths: the rule did nothing that could be told from noise. One more lesson: our numbers at entry (10/19) scored 0.0526 and the 10/27 update scored 0.0697, because the crowd moved toward the wrong answer on the election markets in the last week and we followed it. The election forecasts hang on one vote, so that is one event, not a pattern.

The scorecard used to compare our last number with the market's first price, which flattered whichever side had the later information. It now compares like with like (`vs_market`), and keeps the old comparison as `vs_market_at_entry`.

## The 90-day test
Write 15 to 20 forecasts on the United States and Israel relationship, log the market price beside each one, and score after 90 days. If the record does not beat the market, stop or change the method.
