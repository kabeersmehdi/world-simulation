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
| `guard_resolution` | A resolved forecast with no outcome source, or an open one with a resolution |
| `guard_no_illustrative_in_live` | An illustrative forecast saved in `data/forecasts/` |
| `guard_exclusive_groups` | Open forecasts in one `exclusive_group` (for example rival candidates) adding up to more than 100% |

Each guard has a red-team test that feeds it a bad record and checks it is rejected.

## Scoring
- Brier score on resolved yes/no forecasts, using the last probability made before the deadline.
- Compared against two baselines: the reference-class base rate, and the market price logged with the first update.
- Calibration shown in ten probability bands.
- No claim of an edge until at least 20 forecasts have resolved (`MIN_RESOLVED_FOR_CLAIMS`). Below that the dashboard says "not enough data".

## Sprint to 20 resolutions (started 10/19/2026)
Eighteen forecasts on Polymarket markets that resolve between 10/21 and 11/1 (election results, strikes by 10/31, Iran deadlines, the Bank of Israel decision), plus the open election-held and bloc forecasts, give about 20 resolutions within two weeks. None of them carries an independent news view. Each one uses the market price with one stated rule: prices under 10% or over 90% move 30% closer to the edge (the favorite-longshot bias), and prices in between stay as they are. The sprint tests that rule, not the news pipeline. The election forecasts all hang on one vote, so they are not independent tests.

## The 90-day test
Write 15 to 20 forecasts on the United States and Israel relationship, log the market price beside each one, and score after 90 days. If the record does not beat the market, stop or change the method.
