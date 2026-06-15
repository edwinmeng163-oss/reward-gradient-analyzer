# Codex Prompt Header — RGA project (cat this in front of every Codex task)

> Usage:
>   codex-agent start "$(cat /Users/wmbt7052/Documents/RDG/tools/codex-prompt-header-rga.md; echo; echo '---'; echo; cat /tmp/rga-task.md)" \
>     -m gpt-5.5 -r xhigh -s workspace-write \
>     -d /Users/wmbt7052/Documents/RDG

## Project
You are implementing in **Reward Gradient Analyzer (`rga`)** at
`/Users/wmbt7052/Documents/RDG`. Goal: extract the player-PERCEIVED reward gradient
(reward events, player effort/cost, pacing) from gameplay recordings for game designers.
Read `AGENTS.md` and `docs/research/01-five-directions.md` before substantive work.

## Isolation (binding)
- This is NOT the UEvolve/UnrealMcp project. Do not read, edit, or reference that repo
  or `~/.hermes` memory. Work only inside `/Users/wmbt7052/Documents/RDG`.

## Always-on conventions
- Stay inside the EDIT list. No `git commit/push/checkout/rebase`/index mutation —
  leave a dirty working tree only.
- Python 3.11+, type hints, modules under `src/rga/`; keep `requirements.txt`/`pyproject.toml`
  accurate to imports.
- Perception pipeline = specialist-heavy (ffmpeg + OCR-on-ROI + screen-state/template
  detectors + audio cue) with a VLM used ONLY to review low-confidence candidate frames.
  Do NOT build an "end-to-end VLM reads the whole video" pipeline (it fails at HUD reading
  — VideoGameQA-Bench ~40%).
- Two-level output: detect `reward_moment` first, split into `reward_items` later.
- Precision over recall. Every emitted event carries a confidence and an evidence ref
  (frame index / timestamp).
- Legal: first-party/self-recorded footage under `data/` only; never scrape VODs.

## Provenance
End your run with:
`RGA-PROVENANCE: ticket=<id> | model=gpt-5.5 xhigh | edits=<files> | acceptance=<criteria met>`
