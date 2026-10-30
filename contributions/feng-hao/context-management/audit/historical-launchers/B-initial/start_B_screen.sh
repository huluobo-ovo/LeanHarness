#!/bin/bash
set -euo pipefail
ROOT=/Users/haohao/Downloads/03work-fh
HERE="$(cd -- "$(dirname -- "$0")" && pwd)"
PY="$ROOT/vendor/TUA-Bench/.venv/bin/python"
if [[ -z "${OPENROUTER_API_KEY+x}" && -z "${MSWEA_API_KEY+x}" ]]; then
  echo 'Not started: provider variables are unavailable in this terminal. Run this launcher from a privately configured terminal. Never paste credentials into chat.'
  exit 2
fi
if /usr/bin/screen -ls 2>/dev/null | /usr/bin/grep -q '[.]pe6203-B[[:space:]]'; then
  echo 'No duplicate batch started: screen session pe6203-B already exists.'
  exit 0
fi
"$PY" -B "$HERE/run_B.py"
mkdir -p "$ROOT/results/context-formal"
LOG="$ROOT/results/context-formal/B-screen-$(date +%Y%m%d-%H%M%S).log"
cd "$ROOT"
/usr/bin/screen -dmS pe6203-B /bin/bash -c 'exec /usr/bin/caffeinate -di "$1" -B -u "$2" --live >>"$3" 2>&1' -- "$PY" "$HERE/run_B.py" "$LOG"
echo "Screen launch requested; log: $LOG"
echo 'Confirm actual batch startup using B-progress.json or START B in the log. A background launch request alone does not establish that model calls have begun.'
