---
type: policy
title: Methodology
status: active
generated:
  by: human-reviewed
  at: 2026-10-18
---

# Methodology

## The core rule
Infer motives from evidence, not assumptions. A government's public reason is not the whole story, and a plausible hidden motive is not true just because it fits. The job is to test competing explanations and keep the one the evidence supports best.

Most "4D chess" turns out to be visible incentives: domestic politics, coalition survival, money, military limits, and staying in power. Start there before reaching for a secret plan.

## Evidence labels
Every claim in `data/evidence/` carries exactly one label. The schema rejects anything else.

| Label | Meaning |
|---|---|
| `established_fact` | Supported by reliable, traceable evidence |
| `official_position` | What a leader or institution publicly claims |
| `observed_behavior` | What they have demonstrably done |
| `evidence_backed_inference` | A reasoned reading supported by several pieces of evidence |
| `hypothesis` | Plausible, not established |
| `speculation` | Weak, indirect or insufficient evidence |

A hypothesis is never shown as a fact. Consequential claims carry a source and a confidence level. Evidence against a favored explanation is recorded as carefully as evidence for it (`evidence_against`).

## What to research per country
1. Leadership and institutions: formal power versus real power, factions, veto points
2. Ideology, worldview and religion: only where documented in primary sources
3. Strategic objectives: stated, demonstrated, domestic survival, security
4. Networks: relationships with a type, period, source and confidence. Association is not control.
5. Track record: promises versus actions, tested against several explanations
6. Capabilities and constraints: military, fiscal, legal, coalition math, public opinion
7. Current developments: dated, with publication date and event date kept separate

## Cross-government layer
The United States and Israel are modeled together, with Iran, Hezbollah, the Houthis and the Gulf states as outside players. Scenarios in `data/scenarios/` are modeled pathways, never facts, and the dashboard labels them that way.
