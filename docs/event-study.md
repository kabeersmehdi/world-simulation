---
type: policy
title: Market reactions to past strikes
status: active
generated:
  by: human-reviewed
  at: 2026-10-19
stale_after: 2027-01-19
---

# Market reactions to past strikes

`python -m worldsim prices` fetches daily closes for the assets in `config/assets.json` (oil, gold, oil volatility, the shekel, Israeli stocks, US and Israeli defense, tankers, ZIM, the S&P 500) and measures how each moved after every `strike` or `war` event in `data/timeline/`.

## Method
- **Base:** the last close strictly before the event date.
- **Day k:** the k-th trading close on or after the event date, for windows of 1, 5 and 20 trading days.
- **Benchmark:** US-listed stocks are measured against SPY, so a market-wide day is not mistaken for a war reaction.
- **Normal swing:** the standard deviation of all k-day moves for that asset over the whole sample.
- **Unusual:** the average move is at least 2.0 standard errors from zero (`UNUSUAL_Z`), with 3 or more events.
- **Holds:** still unusual in direction and at least half as big once the single biggest event is dropped (`ROBUST_SHARE = 0.5`). Unusual but not holding means one event, usually the 2026 war, carries the average.
- Events on the same date count once.

## Limits
- About a dozen events. Several sit inside each other's 5- and 20-day windows, which overstates certainty.
- Events are dated by calendar day. A strike late in the evening lands on the next trading day.
- Raw prices are not committed (`data/prices/` is ignored); only the results in `data/eventstudy/` are.
- This describes what happened. It is not a trading signal or investment advice.
