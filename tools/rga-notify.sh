#!/usr/bin/env bash
# RGA desktop notice helper (macOS). Usage: rga-notify.sh "<title>" "<message>"
# Fires a native macOS notification with sound. No-op-safe if osascript is unavailable.
TITLE="${1:-RGA}"
MSG="${2:-}"
# escape double quotes for the AppleScript string literals
TITLE_ESC=${TITLE//\"/\\\"}
MSG_ESC=${MSG//\"/\\\"}
osascript -e "display notification \"${MSG_ESC}\" with title \"${TITLE_ESC}\" sound name \"Glass\"" >/dev/null 2>&1 || true
