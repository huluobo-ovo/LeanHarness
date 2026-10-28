#!/bin/bash
# Run the 40-task set for the main config, then the ablation config.
# Usage: export OPENROUTER_API_KEY=...  then  bash ~/Downloads/run_40.sh

set -u

ROOT=~/pe6203/LeanHarness
FR=$ROOT/contributions/yichen-tang/failure_recovery
LIST=$ROOT/configs/task_list_40.txt
MODEL=openrouter/minimax/minimax-m3.1-flash

cd "$ROOT/vendor/TUA-Bench" || { echo "TUA-Bench folder not found"; exit 1; }

if [ -z "${OPENROUTER_API_KEY:-}" ]; then
  echo "OPENROUTER_API_KEY is not set. Run: export OPENROUTER_API_KEY=<your key>"
  exit 1
fi

# CellProfiler image is amd64 only
export DOCKER_DEFAULT_PLATFORM=linux/amd64

if ! docker info > /dev/null 2>&1; then
  echo "Docker is not running. Start Docker Desktop first."
  exit 1
fi

TASKS=()
while IFS= read -r t || [ -n "$t" ]; do
  t="${t%$'\r'}"
  t="${t## }"; t="${t%% }"
  [ -z "$t" ] && continue
  case "$t" in \#*) continue ;; esac
  if [ ! -d "tasks/$t" ]; then
    echo "Task folder missing: tasks/$t"
    exit 1
  fi
  TASKS+=(-i "$t")
done < "$LIST"

N=$(( ${#TASKS[@]} / 2 ))
echo "Tasks found: $N"
if [ "$N" -ne 40 ]; then
  echo "Expected 40 tasks, stopping."
  exit 1
fi

for CFG in main ablation; do
  echo
  echo "=== $CFG: start $(date '+%Y-%m-%d %H:%M') ==="
  PYTHONPATH="$FR" caffeinate -i uv run harbor run -p tasks "${TASKS[@]}" \
    --agent-import-path failure_recovery_harbor:FailureRecoveryMiniSweAgent \
    -m "$MODEL" \
    --agent-kwarg version=2.4.3 \
    --agent-kwarg config_file="$FR/failure-recovery-$CFG.yaml" \
    --agent-kwarg cost_limit=0.06 \
    -n 1 -o "jobs/fr-$CFG" --yes
  echo "=== $CFG: end $(date '+%Y-%m-%d %H:%M') ==="
done
