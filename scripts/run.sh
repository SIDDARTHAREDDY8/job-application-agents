#!/usr/bin/env bash
# Daily runner for job-application-agents. Called by cron (see install_cron.sh).
#
# Env overrides (all optional):
#   INPUT_FILE  text file with job posts            (default: state/input.txt)
#   MAX_JOBS    max jobs to process per run          (default: 5)
#   RESUME      path to resume PDF                  (default: none)
#   DRY_RUN     1 = draft only, 0 = actually apply  (default: 1)
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_DIR"

if [ -x "$REPO_DIR/.venv/bin/python" ]; then
  PY="$REPO_DIR/.venv/bin/python"
else
  PY="python3"
fi

mkdir -p state/logs
STAMP="$(date +%F_%H-%M)"
LOG="state/logs/run_${STAMP}.log"

INPUT_FILE="${INPUT_FILE:-state/input.txt}"
MAX_JOBS="${MAX_JOBS:-5}"
RESUME="${RESUME:-}"
DRY_RUN="${DRY_RUN:-1}"

if [ ! -f "$INPUT_FILE" ]; then
  echo "[$(date)] No input file at $INPUT_FILE - nothing to do." | tee -a "$LOG"
  exit 0
fi

ARGS=(--input "$INPUT_FILE" --max-jobs "$MAX_JOBS" --state state/applications.json)
if [ "$DRY_RUN" = "1" ]; then
  ARGS+=(--dry-run)
else
  ARGS+=(--board-apply)
fi
if [ -n "$RESUME" ]; then
  ARGS+=(--resume "$RESUME")
fi

echo "[$(date)] Starting run (dry_run=$DRY_RUN, input=$INPUT_FILE)" | tee -a "$LOG"
"$PY" -m src.main "${ARGS[@]}" 2>&1 | tee -a "$LOG"
echo "[$(date)] Done." | tee -a "$LOG"
