# RGA-001 — Technical Spike: deckbuilder `reward_moment` extractor (specialist pipeline)

**Author:** Claude (PM) · **Assignee profile:** `rga` · **Board:** `rga` · **Repo:** `/Users/wmbt7052/Documents/RDG`
**Direction:** #1 (technical spike) from `docs/research/01-five-directions.md`.

## Goal
On ONE deckbuilder (**Slay the Spire** as primary target), build a runnable **specialist
perception pipeline** that turns a gameplay recording into a **`reward_moment` timeline +
reward-density curve**, plus the **eval harness** to measure precision/recall against
hand labels. Prove the riskiest assumption: *can we extract perceived reward moments from
video at usable accuracy?*

## Hermes planning instruction
Decompose this on the `rga` Kanban board into subtasks (e.g. ingestion → OCR-ROI →
screen-state/template → audio cue → fusion → eval/report), then dispatch Codex
(gpt-5.5 xhigh) per subtask using `tools/codex-prompt-header-rga.md`. Run the pipeline,
verify, and comment evidence back on the ticket.

## In scope
- **Ingestion** (`src/rga/ingest.py`): ffmpeg → 1 fps baseline frames (720p) + trigger-based
  local densify (4–8 fps on scene-change/audio-peak); 16 kHz audio extract.
- **OCR-on-ROI** (`src/rga/ocr.py`): PaddleOCR/PP-OCRv5 on fixed HUD ROIs (gold/energy/score)
  + keyword screens ("Choose a Card", "Reward", "Victory", "Shop", "Relic"). Per-game ROI
  config in a JSON template (`configs/slay-the-spire.json`).
- **Screen-state / template detection** (`src/rga/screens.py`): classify reward/shop/victory/
  combat/map screens via color/layout/template matching first (no training needed).
- **Audio cue** (`src/rga/audio.py`): onset/energy peaks + a few CLAP/template cues; used as
  trigger + confidence boost, NOT as sole event source.
- **Fusion** (`src/rga/fuse.py`): interval clustering → `reward_moment` events. Two-level
  output: emit `reward_moment` now; leave a `reward_items` stub for later. Each event has
  `confidence` + `evidence_ref` (frame idx / timestamp).
- **Eval harness** (`src/rga/eval.py`): load hand labels, compute recall/precision/timestamp
  error vs detected events; define the gold-label JSON schema + a labeling note in `docs/`.
- **Outputs**: `reward_moment` timeline JSON + reward-density curve PNG + a short `report.md`.
- **Runner** (`src/rga/cli.py` or `analyze.py`): `python -m rga.cli analyze data/recordings/<clip>.mp4`.

## Out of scope (do NOT build now)
SAM2, cross-game generalization, full multiplicative `reward_score`, complex effort model,
player-voice emotion, real-time, and any **end-to-end "VLM reads the whole video"** path.
A VLM may be used ONLY as an optional reviewer of low-confidence candidate frames.

## Acceptance criteria (measurable)
1. Pipeline runs end-to-end from a clean checkout on a 10–20 min clip placed in
   `data/recordings/` via the documented command, producing timeline JSON + density PNG + report.
2. On hand-labeled **obvious** reward moments: **recall ≥0.60, precision ≥0.80,
   timestamp median error <2s** (precision prioritized — prefer misses over false events).
3. Per-game ROI/template config is data-driven (JSON), not hardcoded constants in logic.
4. `requirements.txt`/`pyproject.toml` accurate; `eval.py` prints the metrics table.
5. Codex left a dirty working tree only (no commits); final report addresses each criterion
   and ends with the `RGA-PROVENANCE:` line.

## Dependency / known gap (flag to PM)
We have **no first-party footage yet**. Build the pipeline + eval harness to run on whatever
is in `data/recordings/`. If no clip is present, self-test on a tiny sample or a few manually
saved screenshots, and clearly report "metrics pending real footage." Sourcing ~10 self-recorded
Slay the Spire clips is the parallel Direction-2 task (RGA-002, to be created).

## Provenance
ticket=RGA-001 · created-by=Claude-PM · 2026-06-15
