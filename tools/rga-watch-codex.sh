#!/usr/bin/env bash
# Watch a codex-agent job for TURN completion, then fire a desktop notice — so nobody
# idle-waits. Relies on the turn-complete signal file written by codex-orchestrator's
# notify-hook on every `agent-turn-complete` (fires even though interactive codex sessions
# stay alive). Run DETACHED after dispatching a Codex job:
#   nohup tools/rga-watch-codex.sh <job_id> "<ticket/label>" >/dev/null 2>&1 & disown
set -u
JOB="${1:?usage: rga-watch-codex.sh <job_id> <label>}"
LABEL="${2:-codex}"
SIG="$HOME/.codex-agent/jobs/${JOB}.turn-complete"
NOTIFY="$(cd "$(dirname "$0")" && pwd)/rga-notify.sh"
for i in $(seq 1 360); do        # up to ~90 min at 15s
  if [ -f "$SIG" ]; then
    "$NOTIFY" "RGA · Codex 完成" "${LABEL}: turn complete — 可复审 (job ${JOB})"
    exit 0
  fi
  if ! tmux has-session -t "codex-agent-${JOB}" 2>/dev/null; then
    "$NOTIFY" "RGA · Codex 结束" "${LABEL}: 会话已结束(无 turn-complete 信号) job ${JOB}"
    exit 0
  fi
  sleep 15
done
"$NOTIFY" "RGA · Codex 超时" "${LABEL}: 90min 未见完成 job ${JOB}"
