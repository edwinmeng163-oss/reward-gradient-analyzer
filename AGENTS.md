# AGENTS.md — RGA (for Codex implementers)

You are implementing in the **Reward Gradient Analyzer (`rga`)** repo at
`/Users/wmbt7052/Documents/RDG`. You were dispatched by Hermes (the `rga` profile) on
behalf of Claude (PM). Honor these rules.

## Provenance (session-header)
- Every Codex task is prefixed with `tools/codex-prompt-header-rga.md`. It carries the
  project identity, the isolation rules, and the always-on conventions. Treat it as
  binding context.
- At the END of your run, append a short provenance block to your final report:
  `RGA-PROVENANCE: ticket=<id> | model=gpt-5.5 xhigh | edits=<files touched> | acceptance=<which criteria you believe are met>`.

## Hard rules
- Stay STRICTLY inside the EDIT list / scope in the per-task prompt.
- Do NOT run `git commit/push/checkout/rebase/reset` or any index mutation. Leave a
  dirty working tree only; the PM stages and commits.
- Do NOT touch unrelated files or other repos (especially never the UEvolve repo).
- Python 3.11+, type hints, small focused modules under `src/rga/`. Add/keep a
  `requirements.txt` or `pyproject.toml` accurate to what you import.
- Precision over recall: if a detector is unsure, prefer to flag low-confidence rather
  than emit a false reward event.
- Legal: only operate on first-party/self-recorded footage placed under `data/`. Never
  add code that scrapes Twitch/YouTube VODs.

## What "done" means
- Code runs from a clean checkout per the task's stated command.
- Acceptance criteria in the ticket are addressed point-by-point in your final report.
- If you could not meet a criterion, say so explicitly with the reason.
