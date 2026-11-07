---
type: policy
title: Player cards
status: active
generated:
  by: human-reviewed
  at: 2026-11-07
stale_after: 2027-02-07
---

# Player cards

Every question here turns on a few people's choices. A card in `data/actors/` records, for one decision-maker, what they want, what they fear, what stops them, who can remove them, the public signs that they are about to move, and their record with dates. Cards are checklists, not models: the tool never runs a simulation of a leader. A person writes an independent forecast by going down the cards and saying what each player does in the scenario.

## Rules
- Every line under wants, fears, constraints and red lines cites an evidence, timeline, forecast or base-rate id, or carries a mark: `(stated)` for the player's own words, `(reported)` for press reports, `(inferred)` for our reading of the record, `(open research)` for a gap. `tests/test_actors.py` rejects an unmarked line.
- Never infer anyone's goals from their religion or associates. Doctrine goes in [the ideology notes](ideology-research.md) with the texts the player cites.
- A card has a date (`as_of`). Old cards are not deleted; they are refreshed and the record grows.
- An independent forecast lists its players on the history entry: `"players": [{"actor": "ac-trump", "does": "..."}]`. The guard rejects an unknown card id.

## The cards on 11/07/2026
| Card | Who |
|---|---|
| `ac-netanyahu` | Caretaker prime minister, Likud |
| `ac-eisenkot` | Yashar leader, reported holder of the first mandate |
| `ac-trump` | President of the United States |
| `ac-iran-leadership` | The Supreme Leader (reported: Mojtaba Khamenei), the Guards and the security council |
| `ac-hezbollah` | Lebanese armed movement |
| `ac-houthis` | Yemeni movement on the Red Sea |

## What this is for
The data is public and the crowd is well calibrated, so the only place an edge can come from is a view of the players that differs from the crowd's and turns out right. The scorecard splits resolved forecasts by view. If independent views do not beat the market view over 30 or more resolutions, the cards stay as reading material and the numbers stay with the crowd.
