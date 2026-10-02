#!/usr/bin/env bash
# Removes the job-application-agents cron job installed by install_cron.sh.
set -euo pipefail

MARKER="# job-application-agents"

if ! command -v crontab >/dev/null 2>&1; then
  echo "No 'crontab' command found on this machine - nothing to remove."
  exit 0
fi

TMP="$(mktemp)"
(crontab -l 2>/dev/null | grep -v "$MARKER" || true) > "$TMP"
crontab "$TMP"
rm "$TMP"
echo "Removed the job-application-agents schedule (if it existed)."
echo "Verify with: crontab -l"
