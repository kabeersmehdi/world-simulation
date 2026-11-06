---
type: log
title: Change log
---

# Change log

## 2026-11-06
- Resolved 17 forecasts: the Oct 27 election set (held as scheduled, Netanyahu bloc 53 vs 48, Likud largest with 27, Together third, no 61-seat bloc, Yisrael Beytenu 5.93%, Amcha under threshold), the five by-Oct-31 strike questions (all no), the Iran concessions by Oct 31 (fees, IAEA visit, uranium: all no), the blockade-end-by-Oct-31 (no) and the ceasefire-through-the-midterms (yes). Outcomes from each market's last saved price before archival, election ones cross-checked against the official CEC results certified Nov 4. Scorecard: 15 hits, 2 misses; the misses are the two bloc-seat calls, where our poll-weighted number (32% Netanyahu bloc wins more seats) lost to the market. fc-il-strike-iraq-by-oct-31 stays open: its market still trades at 19% past deadline, likely disputed.


## 10/19/2026
- Markets now: live quotes for 16 assets (TradingView through a local quote tool, Yahoo as the keyless fallback), a stress read against each asset's past year, and Polymarket's war odds beside it. Added 10 Persian and Arabic feeds (IRNA, Mehr, Fars, BBC Persian, Iran International, Al Manar, Al Masirah, Al Jazeera, Asharq Al-Awsat, BBC Arabic) and `python -m worldsim watch`.
- Forecasts tab rebuilt in plain English (most likely outcome, our number, Polymarket, the gap), Timeline gets Coming up and Most likely outcomes, military forecasts link to past stock reactions, and `dashboard/brief.md` is written on every build for the stocks report.
- Added the strike event study: 15 assets, 11 strike and war events since October 2023, 1, 5 and 20 trading-day moves against each asset's normal swing, with a check that drops the biggest event. New Reactions view and `python -m worldsim prices`.

## 2026-10-19
- Added timing curves from Polymarket ladders (Israel-Iran ceasefire, US strikes before the midterms, blockade end, Hormuz deal, nuclear deal), a backtest of 1,422 resolved geopolitics markets with calibration, Knesset seat polls with bloc totals, and three ceasefire and blockade forecasts started at market.

## 2026-10-18
- First version. Scope narrowed from five governments to two (United States and Israel) so profiles can be kept current by one person.
- Added the Hebrew news and Telegram collector, five leading-indicator collectors, the watch level, base rates, forecast guards, Brier scoring and the dashboard.
- Country profiles seeded with facts checked on 2026-10-18 against the Library of Congress, the White House and Wikipedia. Ideology, objectives, networks and track record sections are open research items.
- Added Polymarket tracking (12 markets) as the crowd baseline, leader polls, a timeline of wars and strikes from October 2023 to the 2026 Iran war, documented backers (US aid agreement, AIPAC committees from FEC filings), and an Iran profile with its constitutional doctrine.
- Forecasts in `data/demo/` are illustrative only. `data/forecasts/` starts empty on purpose.
