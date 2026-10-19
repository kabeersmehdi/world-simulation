# World Simulation

**What it does:** tracks what the United States and Israel say, what they actually do, and what is likely to happen next, with Iran as the main outside player. It pulls Hebrew, Persian, Arabic and English news, reporters' and official Telegram channels, US military aircraft and carrier positions, State Department advisories, leader polls, Polymarket prices and live quotes for oil, defense, shipping and the shekel into one dashboard. Then it makes you write dated, testable forecasts and scores them against the market.

**The point:** the edge is not a secret source. It is being faster on Hebrew sources, watching the public tracks big operations leave, starting from base rates instead of gut feel, and keeping an honest score against the crowd.

## Quick start

Needs Python 3.11 or newer. No installs, no API keys.

```bash
python3 -m worldsim collect          # pull every feed and market, then build the dashboard
python3 -m http.server -d dashboard  # open http://localhost:8000
```

## The whole thing in plain English

1. **Collect.** Every run reads 27 feeds (Hebrew, Persian, Arabic, English), every forecast's Polymarket market, and live quotes for 16 assets. Headlines and short excerpts are saved locally with links. Full articles are never stored.
2. **Tag.** Keyword rules (mostly Hebrew and English; Persian and Arabic for airspace closures) flag eight leading indicators: airspace closures, Home Front Command instructions, reserve call-ups ("Tzav 8"), late-night security cabinet meetings, US departure orders for diplomats, and US tankers, bombers, surveillance planes or carriers in the region, GPS jamming (civil aircraft over Israel or the Gulf reporting degraded GPS), and NASA satellite fire detections at refineries, oil terminals, ports and nuclear sites (optional, needs a free key).
3. **Watch level.** One indicator means little. Two kinds at once is "elevated", three or more is "high". This is a rule of thumb until enough past events are logged against it, and the dashboard says so.
4. **Base rates.** Past strikes and responses between Israel, the US and Iran set the starting odds. With only a handful of comparable events, every number carries a small-sample warning. History sets the starting point, it does not call exact dates.
5. **Forecast.** You write the question, the rule that decides it, a deadline and your probability. The tool logs the market price beside it on the same day.
6. **Score.** Brier scores against the base rate and the market, calibration bands, and no claim of an edge until 20 forecasts have resolved.

## Dashboard views

| View | What it shows |
|---|---|
| Overview | Watch level, market baseline, latest Hebrew headlines, recent timeline |
| Indicators | Each of the eight signals, active or quiet, with the items that triggered it |
| Overview | Markets now (oil, defense, shipping, shekel, with a stress read and Polymarket's war odds), then the watch level and latest headlines |
| News feed | Searchable Hebrew, Persian, Arabic and English headlines, with a translate link on every non-English item |
| Markets | Polymarket prices with change since first logged |
| Forecasts | Your live forecasts, plus clearly marked illustrative examples |
| Polls | Leader preference and approval polls, each row sourced |
| Countries | Profiles for the United States, Israel and Iran |
| Timeline | Wars, strikes and ceasefires from October 2023 to the 2026 Iran war |
| Backers | Aid agreements, political spending from FEC filings, alliances, doctrine |
| Base rates | Starting odds from past events, with lags and the small-sample warning |
| Scenarios | Modeled pathways (labeled as not fact) and market transmission |
| Scorecard | Brier, calibration, comparison with base rate and market |
| Sources | Every evidence record and feed, with blocked feeds listed |

## Writing a forecast

Start from a market so the crowd's number is logged on day one:

```bash
python3 -m worldsim new-forecast --market will-benjamin-netanyahu-be-the-next-prime-minister-of-israel
```

Open the new file in `data/forecasts/`, fill in your probability, the resolution rule, countries and topic, then:

```bash
python3 -m worldsim validate
```

Validation refuses 0% and 100%, deadlines before the start date, and any edit to an earlier probability. To update, add a new entry to `history`. Never change an old one.

## Commands

| Command | Does |
|---|---|
| `python3 -m worldsim collect` | Fetch everything, save new items, rebuild the dashboard |
| `python3 -m worldsim collect --only ynet tg-kann-news` | Fetch only the named sources |
| `python3 -m worldsim build` | Rebuild the dashboard from saved data |
| `python3 -m worldsim validate` | Check every data file against its schema and guards |
| `python3 -m worldsim score` | Print the scorecard |
| `python3 -m worldsim new-forecast --market <slug>` | Start a forecast from a Polymarket market |
| `python3 -m worldsim live` | Live quotes and the stress read |
| `python3 -m worldsim watch --every 15` | Run collect every 15 minutes until stopped |
| `python3 -m worldsim prices` | Refresh daily prices and the strike event study |
| `python3 -m worldsim backtest` | Score resolved Polymarket markets (how good is the baseline?) |
| `python3 -m unittest` | Run the tests (offline, about a second) |

## Adding data

| To add | Put it in | Rules |
|---|---|---|
| A news feed or Telegram channel | `config/sources.json` | `kind` is `rss` or `telegram`; Telegram channels use `https://t.me/s/<channel>` |
| A market | `config/markets.json` | the Polymarket slug and which outcome is "yes" |
| A fact or claim | `data/evidence/` | one label (fact, official position, behavior, inference, hypothesis, speculation) and at least one source |
| A past event | `data/timeline/` | date, category, sources; `verified: false` until checked against a primary or newsroom source |
| A backer or relationship | `data/relationships/` | amount, period, sources, and what the link does not show |
| A poll | `data/polls/` | pollster, fieldwork date, values, source |
| Religious or doctrinal research | `data/evidence/` with topic `doctrine` | anchored on the actor's own words; see `docs/ideology-research.md` |

## Satellite fire alerts (optional)

The NASA FIRMS collector watches refineries, oil terminals, ports and nuclear sites in Iran, the Gulf, Israel and Yemen for fires seen from space. It needs a free key, and everything else runs without it.

1. Ask NASA for a key at https://firms.modaps.eosdis.nasa.gov/api/map_key/ (an email address is all it takes).
2. Set it in the shell that runs `collect`:

```bash
export FIRMS_MAP_KEY="..."
```

3. Check it:

```bash
python3 -m worldsim collect --only firms-iran-gulf firms-israel firms-yemen
```

Without the key you see `skip firms-...: not configured`, which is expected. For the GitHub Actions `collect` workflow, add the key as a repository secret named `FIRMS_MAP_KEY`. Sites and thresholds are in `docs/indicators.md`.

## Live TradingView quotes (optional)

Without setup, Markets now uses Yahoo Finance (about 15 minutes delayed). To use TradingView instead, copy `config/local.example.json` to `config/local.json` and point `tradingview_tool` at a local quote tool that has `scripts/snapshot_quotes.py`. It runs as a separate program and `config/local.json` is never committed.

## Running it on a schedule

The simplest way is to leave this running in a terminal:

```bash
python3 -m worldsim watch --every 15
```

Or 
On a Mac, a cron entry every two hours:

```bash
crontab -e
```

Then add this line (with your own path):

```
0 */2 * * * cd /path/to/world-simulation && /usr/bin/python3 -m worldsim collect >> collect.log 2>&1
```

The GitHub Actions `collect` workflow can also be run by hand from the Actions tab. It builds the dashboard and attaches it as a downloadable file instead of committing outlets' headlines to the repo.

## Honest limits

- The watch level is not calibrated yet. Treat it as a prompt to look closer, not a prediction.
- Many military flights switch transponders off. A quiet sky proves nothing.
- Home Front Command's own alert feed, the US Embassy Israel alerts page and Israel Hayom block automated requests, so they are listed as blocked rather than scraped.
- Times of Israel refuses cloud servers such as GitHub Actions, so those runs fall back to Google News's feed of its headlines, which can lag by an hour or more.
- Telegram posts are unverified signals, never facts.
- Timeline and base-rate entries sourced to reference sites are marked to verify.
- Nothing here is investment advice. A market price is the crowd's probability, not a fact.

## Layout

```
worldsim/        the code: collectors, tagging, watch level, guards, scoring, build
schemas/         JSON contracts for every data type
config/          feeds and markets
data/            evidence, timeline, relationships, polls, base rates, forecasts, market prices
countries/       country profiles (markdown)
docs/            method, source policy, indicator rules, forecasting rules
dashboard/       the static dashboard
tests/           offline tests and saved fixtures
index.md         the knowledge index (Open Knowledge Format v0.2)
```
