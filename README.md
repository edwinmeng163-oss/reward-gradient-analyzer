# RGA — Reward Gradient Analyzer

Analyze gameplay recordings to extract the player-**perceived** reward gradient
(reward events, player effort/cost, pacing, feedback intensity) and help game
designers judge reward pacing.

- **Operating model & isolation:** see [CLAUDE.md](CLAUDE.md).
- **Codex conventions:** see [AGENTS.md](AGENTS.md).
- **Research basis & strategy:** see [docs/research/01-five-directions.md](docs/research/01-five-directions.md).

## Roles
- **Claude** = PM (tickets + acceptance) · **Hermes `rga` profile** = planning/build-loop/triage ·
  **Codex gpt-5.5 xhigh** = implementation.

## First workstream
Direction 1 — technical spike: specialist perception pipeline on one deckbuilder
(Slay the Spire), extract `reward_moment` timeline + reward-density curve.
Acceptance: recall ≥0.6, precision ≥0.8, timestamp median error <2s on obvious events.

## Layout
```
src/rga/      pipeline code
data/         recordings + annotations (gitignored)
notebooks/    exploration
docs/         design + research
tools/        agent prompt headers / scripts
tickets/      PM work-order drafts
```
