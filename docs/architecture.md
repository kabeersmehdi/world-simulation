---
type: reference
title: Architecture
status: active
generated:
  by: human-reviewed
  at: 2026-10-18
---

# Architecture

A straight line of stages passing JSON. Each stage checks its input and output against a schema in `schemas/` and fails loud on bad data. No agents run inside the tool.

```
collect  ->  tag  ->  store  ->  build  ->  dashboard
(feeds)     (signals)  (data/observations)  (dashboard/data.json)

forecasts + evidence + base rates  ->  guards  ->  score  ->  dashboard
```

| Stage | Module | Contract |
|---|---|---|
| Fetch feeds | `worldsim/collectors/` | raw text in, observation records out |
| Tag indicators | `worldsim/signals.py` | `observation.schema.json` |
| Store | `worldsim/store.py` | one JSON-lines file per day, deduplicated by id |
| Watch level | `worldsim/watch.py` | observations in, level per indicator out |
| Forecast guards | `worldsim/forecasts.py` | `forecast.schema.json` plus the guards |
| Score | `worldsim/scoring.py` | Brier, calibration, baselines |
| Base rates | `worldsim/baserates.py` | `baserate.schema.json` |
| Market baseline | `worldsim/markets.py` | `market_price.schema.json`, one snapshot per run per market |
| Polls | `worldsim/polls.py` | `poll.schema.json` |
| Timeline and backers | `worldsim/build.py` | `event.schema.json`, `relationship.schema.json` |
| Build | `worldsim/build.py` | everything into `dashboard/data.json` |

## Tests
`python -m unittest` runs fully offline. Collectors take an injected fetch function, so tests use saved fixtures in `tests/fixtures/` and never touch the network. Builds in tests write to a temporary folder, never the real `data/`.

## Adding a source
Add an entry to `config/sources.json` with an `id`, `kind` (`rss` or `telegram`), `url`, `lang` and `tier`. Then run `python -m worldsim collect --only <id>` to check it.
