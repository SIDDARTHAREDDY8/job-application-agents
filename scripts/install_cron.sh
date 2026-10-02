#!/usr/bin/env bash
# Installs a cron job that runs the agents on a schedule.
#
# Usage:
#   ./scripts/install_cron.sh                              # daily 09:30, dry-run (safe)
#   ./scripts/install_cron.sh --time 18:00 --max-jobs 10   # daily 6pm, 10 jobs, dry-run
#   ./scripts/install_cron.sh --live --resume resume.pdf   # daily 09:30, ACTUALLY APPLIES
#
# Flags:
#   --time HH:MM     run time (default 09:30)
#   --max-jobs N     jobs per run (default 5)
#   --resume PATH    resume PDF (needed for --live)
#   --live           actually send/submit instead of drafting
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
MARKER="# job-application-agents"

TIME="09:30"
MAX_JOBS="5"
RESUME=""
LIVE="0"

while [ $# -gt 0 ]; do
  case "$1" in
    --time) TIME="$2"; shift 2 ;;
    --max-jobs) MAX_JOBS="$2"; shift 2 ;;
    --resume) RESUME="$2"; shift 2 ;;
    --live) LIVE="1"; shift ;;
    *) echo "Unknown flag: $1"; exit 1 ;;
  esac
done

HH="${TIME%%:*}"; MM="${TIME##*:}"
if ! [[ "$HH" =~ ^[0-9]{1,2}$ && "$MM" =~ ^[0-9]{1,2}$ ]]; then
  echo "Bad --time '$TIME'. Use HH:MM, e.g. 09:30"
  exit 1
fi
# strip leading zeros for cron (08 -> 8)
HH="$((10#$HH))"; MM="$((10#$MM))"

# The cron reads this file every run - put real job posts here.
if [ ! -f "$REPO_DIR/state/input.txt" ]; then
  mkdir -p "$REPO_DIR/state"
  cp "$REPO_DIR/examples/sample_signal.txt" "$REPO_DIR/state/input.txt"
  echo "Created state/input.txt (sample inside)."
fi

DRY_RUN="1"; MODE="dry-run (drafts only, sends nothing)"
if [ "$LIVE" = "1" ]; then
  DRY_RUN="0"; MODE="LIVE (actually applies)"
  if [ -z "$RESUME" ]; then
    echo "Note: --live without --resume: emails go without attachment, board uploads skipped."
  fi
fi

CRON_LINE="$MM $HH * * * PATH=/usr/local/bin:/usr/bin:/bin INPUT_FILE=$REPO_DIR/state/input.txt MAX_JOBS=$MAX_JOBS RESUME=$RESUME DRY_RUN=$DRY_RUN $REPO_DIR/scripts/run.sh >> $REPO_DIR/state/logs/cron.log 2>&1 $MARKER"

# Remove any old entry we installed, then add the new one (no duplicates).
if ! command -v crontab >/dev/null 2>&1; then
  echo ""
  echo "No 'crontab' command found on this machine, so nothing was installed."
  echo "Paste this line into your scheduler (cron, or any cron replacement):"
  echo ""
  echo "  $CRON_LINE"
  echo ""
  echo "On Debian/Ubuntu: sudo apt install cron. On macOS, cron is built in."
  exit 0
fi
TMP="$(mktemp)"
(crontab -l 2>/dev/null | grep -v "$MARKER" || true) > "$TMP"
echo "$CRON_LINE" >> "$TMP"
crontab "$TMP"
rm "$TMP"

echo ""
echo "Installed: every day at $TIME, mode: $MODE"
echo "  Input file : $REPO_DIR/state/input.txt  <-- paste real job posts here"
echo "  Results    : $REPO_DIR/state/applications.json"
echo "  Logs       : $REPO_DIR/state/logs/"
echo ""
echo "Verify with:  crontab -l"
echo "Remove with:  ./scripts/uninstall_cron.sh"
