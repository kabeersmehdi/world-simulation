---
type: policy
title: Do the indicators move before Polymarket?
status: active
generated:
  by: human-reviewed
  at: 2026-10-19
stale_after: 2027-01-19
---

# Do the indicators move before Polymarket?

**Short answer: no tested lead.** From January to October 2026, none of the indicators we could test moved before Polymarket prices in a way that holds up. The one hit, Home Front Command posts, comes from a single day (the start of the war on 28 February). Thin markets are not worse calibrated than big ones either. One small hint is worth watching: markets with $8k to $40k traded overpriced long shots at 7 days out. That hint is not a trade yet.

Run it yourself:

```bash
python3 -m worldsim leadlag --backfill     # rebuild past firings (slow, up to 2 hours), then test
python3 -m worldsim leadlag                # test again on saved firings and prices
python3 -m worldsim backtest --by-volume   # thin versus big markets, no network
```

Results are saved in `data/leadlag/result.json` and `data/backtests/by-volume.json`.

## The question

Every input here is public and the math is standard, so an edge has only two places to hide:

1. **Speed.** An indicator (a Hebrew Home Front Command post, a State Department departure order) fires before the crowd prices the news.
2. **Thin markets.** Small markets with few traders are priced worse than big ones.

This page tests both.

## Part 1: lead-lag

### What was tested

**Indicator history.** The live log (`data/observations`) only starts on 19 October 2026, which is far too short. So `worldsim/backfill.py` rebuilds the past from two free sources and tags it with the same keyword rules the live collector uses:

| Source | Covered | Firings |
|---|---|---|
| Amit Segal (Telegram, Hebrew) | 1 Jan to 19 Oct 2026, 9,782 posts | 105 Home Front, 12 late-night cabinet, 4 reserves, 2 airspace |
| Abu Ali Express (Telegram, Hebrew) | 1 Jan to 19 Oct 2026, 15,270 posts | 38 Home Front, 7 airspace, 3 reserves, 3 late-night cabinet |
| IDF (Telegram, English) | 1 Jan to 17 Oct 2026, 3,103 posts | 847 Home Front |
| Kan News (Telegram, Hebrew) | 2 Jan to 26 Mar 2026 (the channel went quiet), 114 posts | none |
| Al Masirah (Telegram, Arabic) | 1 Jan to 19 Oct 2026, 18,889 posts | 4 airspace |
| State Department advisories (Wayback Machine copies of the feed) | 138 daily copies, 16 Jan to 17 Oct 2026 | 7 departure updates |

Only the post id, time and indicator are kept. No post text is stored.

**Not tested, and why:**

| Indicator | Why not |
|---|---|
| GPS jamming | No free hourly history. gpsjam.org keeps daily maps, but reading them needs an H3 hex library, which breaks the standard-library rule. |
| NASA FIRMS fires | History needs a free key, and none is set. |
| Airline cancellations | The repo has no airline collector, so there is nothing to test. |
| US military moves | The aircraft feed is live only and the fleet tracker is weekly. 3 firings, all in the live log, none overlapping a market. Since 11/07/2026 every collect run logs the hourly tanker, bomber and surveillance counts to `data/signals/aircraft.jsonl` (zeros included) so this can be tested once the log is long enough. |

**Markets.** 845 Polymarket markets on Israel and Iran security, with hourly prices: the 16 security markets in `config/markets.json` (election and coalition markets left out, since an air raid siren is not news about seat counts) plus 829 resolved strike, ceasefire, blockade and nuclear markets from the backtest that closed in 2026. 823 had enough hourly prices to use.

### How it works

1. **Onsets, not firings.** On a war day the IDF channel mentions Home Front Command dozens of times. Only the first firing after 48 quiet hours counts. That turns 847 IDF firings into a handful of onsets.
2. **Move after, move before.** For each onset and each market open at that moment, measure the absolute price change over the next 1, 6, 24 and 72 hours, and over the same span before it.
3. **The onset's own hour is skipped.** Prices are hourly and a 15-minute collector sees a post a few minutes late, so any move inside that hour is one you could not have traded. The "after" window starts at the next full hour.
4. **Random baseline.** Each of 1,000 draws moves every onset to a random time inside its own source's coverage and measures the same thing. The p-value is the share of draws with an average move at least as big as the real one.
5. **One event cannot carry it.** The test reruns without the onset that moved markets most. A lead that disappears without it is labeled "one event only".

### Results

Average absolute move in the Yes price, in probability points. "Random" is the average at random times.

| Indicator | Onsets | 1 hour after / random | 6 hours | 24 hours | 72 hours | Verdict |
|---|---|---|---|---|---|---|
| Home Front Command | 30 | 1.69 / 0.66 (p 0.003) | 2.47 / 1.82 (p 0.03) | 3.77 / 3.65 (p 0.37) | 5.08 / 5.80 (p 0.89) | one event only |
| Airspace closure | 10 | 0.76 / 0.65 (p 0.22) | 1.68 / 1.82 | 3.36 / 3.66 | 4.33 / 5.81 | no lead |
| Late-night cabinet | 12 | 0.77 / 0.65 (p 0.19) | 1.82 / 1.82 | 3.78 / 3.66 | 5.95 / 5.81 | no lead |
| Reserve call-ups | 5 | 0.85 / 0.65 | 1.93 / 1.81 | 3.54 / 3.66 | 5.96 / 5.85 | too few to judge |
| State Dept departure orders | 4 | 0.94 / 0.62 | 1.98 / 1.75 | 4.69 / 3.51 | 6.19 / 5.69 | too few to judge |

**Home Front Command, in detail.** The 1-hour and 6-hour results look strong, but they are one day. Without the onset at 06:00 UTC on 28 February 2026, the 1-hour move falls to 0.76 points (p 0.15) and the 6-hour move to 2.29 (p 0.06). Neither clears the bar. The moves before onsets look like random times, so this is not markets moving first either.

That one day is still worth knowing, hour by hour:

| UTC, 28 Feb 2026 | What happened |
|---|---|
| 06:16 | First Home Front Command post (Abu Ali Express), then IDF at 06:24 |
| 06:00 to 07:00 | Average market move 1.9 points (normal is about 0.7) |
| 07:00 to 08:00 | Average market move 18.1 points across 72 markets |
| 08:07 onward | Home Front posts on every channel |

On the opening morning of the war, the first Hebrew Home Front post came roughly an hour before Polymarket repriced. That is a single event. It tells you to watch the first Home Front onset after a long quiet spell, but it is not a tested edge, and the next war will not open the same way.

**Departure orders** show a hint the other way: across the 4 onsets, prices had already moved more in the 1 and 6 hours before the update than at random times (p 0.01 and 0.03). If that held with more data, it would mean the advisory feed lags the market. Four onsets prove nothing.

### Honest limits

- **Small samples.** 30 Home Front onsets in ten months, and fewer for everything else. One onset touches up to 70 markets at once, so the onset count is the fair sample size, not the market-pair count.
- **Hourly prices.** A lead shorter than an hour cannot be seen at all. A market that reacts in 10 minutes looks like "no lead", which is also the right answer for anyone trading off a 15-minute collector.
- **Absolute moves.** The test asks whether something happens, not which way. A tradable signal also needs a direction.
- **Keyword rules as they are today.** Persian and Arabic feeds only carry the airspace phrase, so they barely fire. Better keywords could change the answer for those feeds.
- **One regime.** 2026 had one war start, a pause, a collapse and a long ceasefire. The test has seen one war start.

## Part 2: are thin markets worse calibrated?

The backtest (`data/backtests/polymarket-geopolitics.json`, 1,422 resolved markets of at least $10k traded) is split into four equal groups by dollars traded. **Calibration error** is the gap between the average price and how often the event happened, across ten price bands. **Long-shot gap** is the average price minus how often it happened, for markets priced under 30%. A positive gap means long shots were overpriced. Every thin-minus-big gap has a 95% range from resampling whole events, because ladder markets on one event move together.

| Volume | Events | Brier, 7 days | Calibration error, 7 days | Long-shot gap, 7 days |
|---|---|---|---|---|
| $10k to $41k | 112 | 0.075 | 0.077 | +5.9 pts |
| $41k to $113k | 128 | 0.115 | 0.059 | +0.3 |
| $113k to $578k | 138 | 0.101 | 0.071 | -0.5 |
| $578k to $269M | 110 | 0.110 | 0.082 | -3.5 |

Thinnest minus biggest:

| Days before close | Calibration error | Brier | Long-shot gap |
|---|---|---|---|
| 30 | +0.02 (range -0.07 to +0.09) | -0.07 (-0.12 to 0.00) | +3.7 pts (-6.1 to +12.6) |
| 7 | -0.01 (-0.07 to +0.07) | -0.04 (-0.08 to +0.01) | **+9.4 pts (+4.6 to +15.5)** |
| 1 | -0.04 (-0.08 to +0.02) | -0.03 (-0.07 to +0.02) | +6.0 pts (+0.5 to +11.4) |

**Calibration:** no difference. Thin markets even score a slightly better Brier, most likely because they are easier questions (far-out ladder rungs that sit near zero and resolve No), not because thin traders are smarter.

**Long shots:** at 7 days out, the $10k to $41k group priced long shots 5.9 points above how often they happened (range +2.8 to +9.3), while big markets priced them 3.5 points below.

**Under $10k.** The backtest skips markets under $10k. A one-off pull with no floor added 385 such markets (82 events, 1,807 in all). Split into five groups, the under-$8k group shows **no** long-shot overpricing (+1.0 point at 7 days, range -2.6 to +6.3) and no worse calibration. The overpricing sits only in the $8k to $40k band. A real thin-market effect should get stronger as markets get thinner, and this one does not. Together with nine comparisons (three horizons, three measures), the honest read is a hint, not a finding.

Even if it is real, selling long shots in $10k to $40k markets earns about 6 cents per contract before the bid-ask spread, which in markets that thin can be several cents. And 2026 was a year when most "strike by date X" questions resolved No, which flatters anyone who sold long shots.

## What would change the answer

- **More onsets.** Rerun every quarter. The live log adds firings from every `collect`, and `--backfill` refreshes the Telegram and advisory history.
- **Direction.** Add a sign per market (escalation up or down) so a lead, if one shows up, comes with a trade direction.
- **Faster prices.** Polymarket trade data at minute resolution would show leads shorter than an hour.
- **The missing indicators.** GPS jamming and FIRMS fires need a history source before they can be tested.
- **Long shots, out of sample.** Track $8k to $40k long shots from now on, with real bid and ask prices, before putting any money behind it.
