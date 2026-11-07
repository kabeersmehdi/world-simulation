---
type: policy
title: Do the fear gauges move before Polymarket?
status: active
generated:
  by: human-reviewed
  at: 2026-11-07
stale_after: 2027-02-07
---

# Do the fear gauges move before Polymarket?

**Short answer: no.** Tested on 823 Polymarket strike and ceasefire markets from 01/01/2026 to 11/07/2026, none of eleven fear gauges moved before the crowd in a way that holds up. Three of them (the VIX, the Brent-WTI spread and Elbit) moved *after* the crowd: Polymarket prices were already moving in the days before the gauge fired. The one firing that looks like a tell is oil options fear (OVX) jumping on 02/27/2026, the day before the war began, and Brent on 02/18. Across the year those gauges fired 9 and 13 times, and the rest were noise. A gauge that is right once in nine firings is not a signal you can trade.

| Gauge | Firings | 24h after / random (pts) | 72h after / random (pts) | Read |
|---|---|---|---|---|
| Oil options fear (OVX) | 9 | 4.0 / 3.6 (p 0.24) | 6.6 / 6.0 (p 0.26) | too few onsets to judge (9) |
| Stock options fear (VIX) | 7 | 3.9 / 3.6 (p 0.33) | 6.6 / 5.9 (p 0.28) | too few onsets to judge (7) (crowd moved first) |
| S&P tail-risk index (SKEW) | 10 | 3.1 / 3.6 (p 0.74) | 5.0 / 5.9 (p 0.83) | no lead |
| Brent minus WTI (seaborne oil premium) | 7 | 4.2 / 3.6 (p 0.21) | 7.0 / 5.9 (p 0.18) | too few onsets to judge (7) (crowd moved first) |
| Brent crude | 13 | 4.3 / 3.6 (p 0.12) | 6.6 / 6.0 (p 0.20) | no lead |
| Gold | 11 | 3.6 / 3.6 (p 0.50) | 7.0 / 5.9 (p 0.12) | no lead |
| Dollar in shekels (shekel weakens) | 10 | 2.9 / 3.6 (p 0.87) | 4.8 / 5.9 (p 0.88) | no lead |
| US defense ETF against the S&P (ITA/SPY) | 11 | 3.0 / 3.6 (p 0.81) | 5.3 / 5.9 (p 0.76) | no lead |
| Elbit Systems | 8 | 3.9 / 3.6 (p 0.33) | 7.5 / 5.9 (p 0.07) | too few onsets to judge (8) (crowd moved first) |
| Frontline (crude tankers) | 13 | 4.0 / 3.6 (p 0.25) | 5.4 / 6.0 (p 0.78) | no lead |
| Tel Aviv 125 (falls) | 10 | 3.8 / 3.5 (p 0.30) | 5.7 / 5.9 (p 0.53) | no lead |

"Pts" are probability points of absolute move in the Yes price, averaged over every open market. "Random" is the same measurement on random trading days from the gauge's own calendar. "Too few onsets" means under 10 firings overlapped an open market, so the test cannot say either way.

Run it yourself:

```bash
python3 -m worldsim fear      # fetches the daily closes it lacks, reads the lead-lag price cache, writes data/fear/result.json
```

The hourly Polymarket prices come from the lead-lag test's cache (`python3 -m worldsim leadlag` fetches them, about 25 minutes the first time).

## The idea
People who know something hedge first, and hedges leave a price with a timestamp. Oil option prices, stock option prices, the seaborne oil premium, gold, the shekel, defense stocks and tanker stocks all carry that hedging. If one of them jumps before the crowd's strike odds move, that is a lead you could act on. If the crowd was already moving, both are reacting to the same headline.

## The gauges
| Gauge | What it is | Fires when |
|---|---|---|
| Oil options fear (OVX) | Implied volatility of oil | it rises |
| Stock options fear (VIX) | Implied volatility of the S&P 500 | it rises |
| S&P tail-risk index (SKEW) | Price of crash protection on the S&P 500 | it rises |
| Brent minus WTI (seaborne oil premium) | What seaborne crude costs over US crude | it widens |
| Brent crude | The oil price itself | it rises |
| Gold | The classic safety trade | it rises |
| Dollar in shekels (shekel weakens) | Israel's currency | the shekel falls |
| US defense ETF against the S&P (ITA/SPY) | Defense stocks relative to the market | they outperform |
| Elbit Systems | Israel's largest defense company | it rises |
| Frontline (crude tankers) | Tanker rates, through the stock | it rises |
| Tel Aviv 125 (falls) | Israel's stock index | it falls |

## How it works
1. A gauge **fires** on a trading day its change is at least `big_move_sd = 1.5` normal daily swings in the fear direction, where the normal swing is the standard deviation of its daily changes over the trailing 252 trading days. A level (OVX, VIX, SKEW, the spread) uses the plain change; a price uses the log return. After a firing, `quiet_days = 5` trading days must pass before the gauge can fire again, so a wild week counts once.
2. The firing is placed at the US close, `close_hour_utc = 21`. The move in every open Polymarket strike and ceasefire market is measured from the next full hour over 24, 72, 120 hours, and the move over the same span before the close.
3. The baseline draws the same number of random trading days from the gauge's own calendar, at the same close hour, 1,000 times. The p-value is the share of draws with an average move at least as big as the real one.
4. The largest firing is dropped once. A lead that disappears without it is labeled "one event only".

The reading rules are the lead-lag test's: a lead needs the move after the firing to beat random (p under 0.05) while the move before does not, and at least 10 firings that overlapped an open market. Settings live in `config/fear.json` and are locked to this page by a test.

## Limits
- Daily closes hide anything that happens inside the day. A gauge that jumps at 10 AM and a crowd that moves at 11 AM look simultaneous here.
- The markets are the same 845 Polymarket strike and ceasefire questions the lead-lag test used, from 01/01/2026. One firing touches many markets at once, so the firing count is the fair sample, not the pair count.
- Option-level data for single names (put/call skew on Lockheed or Elbit) is not free. OVX, VIX and SKEW stand in for it.
- This says whether the gauges lead the crowd. It does not say the crowd is wrong.
