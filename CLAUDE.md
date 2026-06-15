# CLAUDE.md — RGA project operating model (read this first)

**Project:** Reward Gradient Analyzer (`rga`) — analyze gameplay recordings to
extract the player-**perceived** reward gradient for game designers.
**Repo root:** `/Users/wmbt7052/Documents/RDG`
**Research basis:** `docs/research/` (framework, 5 codex reports, web-grounded
research, and the 5 startup directions). Read `docs/research/01-five-directions.md`
before any substantive planning.

---

## 1. Three-role operating model

```
Claude (PM)            Hermes (rga profile)          Codex (gpt-5.5 / xhigh)
─────────────          ────────────────────          ──────────────────────
writes work orders  →  claims ticket, plans on    →  implements in repo,
+ acceptance criteria  Kanban (decompose/specify),    leaves dirty working tree,
reviews & accepts      runs build loop, triages       session-header provenance
(kanban complete)      dispatches Codex via            (no commits/pushes)
                       codex-agent
```

- **Claude = PM/reviewer.** Creates Kanban tickets with crisp acceptance criteria,
  reviews Codex output, accepts/blocks. Does NOT hand-write feature code unless it
  is a tiny mechanical fix.
- **Hermes (`rga` profile) = planner/orchestrator.** Claims a ready ticket, does the
  Kanban planning (decompose into subtasks, specify), runs the build/verify loop,
  triages failures, and dispatches Codex for implementation.
- **Codex (gpt-5.5, xhigh) = implementer.** Receives a focused EDIT list + the project
  prompt header, edits files, reports. Leaves changes in the working tree only.

Flow for every unit of work: **Claude ticket → Hermes Kanban planning → Hermes dispatches Codex → Codex implements → Hermes verifies → Claude accepts.**

---

## 2. ISOLATION CONTRACT (do not pollute UEvolve / other Hermes projects)

This is a hard requirement. The machine also runs the **UEvolve/UnrealMcp** project on
Hermes's `default` profile. RGA must stay fully isolated.

- **Hermes profile:** ALWAYS use the **`rga`** profile for this project. NEVER use
  `default` (that is UEvolve). Run it via its wrapper alias `rga` or
  `hermes --profile rga ...` if supported; never plain `hermes` (that resolves to the
  sticky default).
- **Hermes memory:** RGA facts go ONLY into the `rga` profile's own `MEMORY.md`.
  NEVER read or write `~/.hermes/MEMORY.md` or `~/.hermes/memories/MEMORY.md`
  (those are UEvolve/global). Do not copy UEvolve memory into `rga`.
- **Skills:** the `rga` profile maintains its OWN enabled-skill set and updates them
  independently. Do not modify the `default` profile's skills for RGA reasons.
- **Kanban:** all RGA tickets live on the **`rga` board only** (`--board rga`).
  Never put RGA tickets on UEvolve boards or vice versa.
- **Codex:** ALWAYS dispatch with `-d /Users/wmbt7052/Documents/RDG` and the RGA
  header (`tools/codex-prompt-header-rga.md`). Never point Codex at the UEvolve repo
  for RGA work, and never reuse the UEvolve `codex-prompt-header.md`.
- **Claude PM memory:** lives in this session's Claude memory dir
  (`~/.claude/projects/-Users-wmbt7052-Documents-topo/memory/`). Keep RGA project
  facts there; do not write RGA facts into any Hermes memory.

---

## 3. Ticket / acceptance workflow (Kanban)

- Board slug: **`rga`**. Default assignee profile: **`rga`**.
- Claude creates a ticket per workstream with: **goal, scope (EDIT list / out-of-scope),
  acceptance criteria (measurable), and provenance note**.
- Hermes claims (`kanban claim`), plans (decompose/specify), dispatches Codex, runs
  verification, and comments evidence back on the ticket.
- Claude reviews the ticket's evidence and `complete`s or `block`s it.
- Ticket markdown drafts also kept in `tickets/` for human readability.

### Notifications (no idle-waiting)
- **After dispatching a Codex job**, Hermes launches a detached watcher so a desktop notice
  fires the moment Codex finishes a turn (ready for review):
  `nohup tools/rga-watch-codex.sh <job_id> "<ticket>" >/dev/null 2>&1 & disown`
- **When Hermes marks a ticket done**, it fires a desktop notice:
  `tools/rga-notify.sh "RGA · 工单完成" "<ticket> ✓ done"`
- Both use `tools/rga-notify.sh` (macOS `osascript`). Mechanism: codex-orchestrator writes
  `~/.codex-agent/jobs/<id>.turn-complete` on every `agent-turn-complete` (fires even though
  the interactive codex session stays alive — so it's reliable). Nobody should sit and idle-wait.

---

## 4. Repo conventions

- **Language:** Python 3.11+ for the perception/analysis pipeline; Markdown reports.
- **Layout:** `src/rga/` code · `data/` recordings+annotations (gitignored) ·
  `notebooks/` exploration · `docs/` design+research · `tools/` agent headers/scripts ·
  `tickets/` PM work-order drafts.
- **No destructive git from Codex/Hermes:** no `commit`/`push`/`checkout`/`rebase`/
  index mutation. Codex leaves a dirty working tree; the PM (Claude) stages and commits.
- **Precision over recall** in the perception pipeline; never present a finding without
  evidence (clip/timestamp/metric/confidence).
- **Legal guardrail:** training and client-facing analysis use FIRST-PARTY / self-recorded
  footage only. Public VODs are reference-only — never training data, never redistributed.
