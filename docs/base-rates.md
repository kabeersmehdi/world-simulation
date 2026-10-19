---
type: policy
title: Base rates
status: active
generated:
  by: human-reviewed
  at: 2026-10-18
---

# Base rates

History sets the **starting odds**. It does not call exact dates.

## How it works
A reference class in `data/baserates/` is a list of comparable past events: a trigger, whether there was a response, and when. `worldsim/baserates.py` turns it into:

- **Response rate**, with Laplace smoothing: (responses + 1) / (events + 2). With 3 events and 3 responses this gives 80%, not 100%, which is the honest answer from so little data.
- **Lag in days** from trigger to response: median, shortest, longest.
- **Chance of a response within N days**: the share of past events that responded within N days, smoothed the same way.

## The small-sample warning
Fewer than 20 events (`SMALL_SAMPLE`) gets a warning on every number. For Israel and Iran there are only a handful of truly comparable direct exchanges. With that few, patterns will appear that are just noise. Treat the output as a starting point, then move off it with current evidence.

## Rules
- Write the inclusion rule before adding events, so you cannot pick cases that fit.
- Every event needs a source. Events not yet checked against a primary or newsroom source are marked `verified: false` and shown that way.
