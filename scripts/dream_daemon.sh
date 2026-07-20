#!/usr/bin/env bash
# Autonomous discovery daemon: run the Dream loop every 5 minutes, each run capped at 280s,
# and push any new commits to GitHub. This keeps the Automated Computer Scientist "awake",
# building and committing on its own.
#
#   bash scripts/dream_daemon.sh              # run forever (Ctrl-C to stop)
#   DREAM_INTERVAL=300 DREAM_TIMEOUT=280 bash scripts/dream_daemon.sh
#   DREAM_MAX_CYCLES=3 bash scripts/dream_daemon.sh   # bounded (e.g. for testing)
#
# Notes:
#  * The per-run 280s `timeout` guards against a hung experiment; a timeout is logged, not fatal.
#  * Once the pending backlog is exhausted the loop is a no-op until a capability's dated
#    certification lapses (decay) or a new Dream is added to the backlog — the daemon then
#    resumes committing automatically.
set -u

cd "$(dirname "$0")/.." || exit 1
REPO="$PWD"
export PYTHONPATH="$REPO"
export HF_HOME="${HF_HOME:-/workspace/hf_cache}"

BRANCH="${DREAM_BRANCH:-claude/capability-discovery-platform-0cti9v}"
INTERVAL="${DREAM_INTERVAL:-300}"     # seconds between cycles (5 min)
RUN_TIMEOUT="${DREAM_TIMEOUT:-280}"   # per-cycle hard cap
MAX_CYCLES="${DREAM_MAX_CYCLES:-0}"   # 0 = run forever

log() { echo "[dream-daemon $(date -Is)] $*"; }

cycle=0
while :; do
  cycle=$((cycle + 1))
  log "cycle ${cycle}: running loop (timeout ${RUN_TIMEOUT}s)"
  before=$(git rev-parse HEAD 2>/dev/null)

  if timeout "${RUN_TIMEOUT}" python scripts/dream_loop.py; then
    log "cycle ${cycle}: loop finished"
  else
    rc=$?
    [ "$rc" -eq 124 ] && log "cycle ${cycle}: TIMEOUT after ${RUN_TIMEOUT}s (non-fatal)" \
                      || log "cycle ${cycle}: loop exited rc=${rc} (non-fatal)"
  fi

  after=$(git rev-parse HEAD 2>/dev/null)
  if [ "${before}" != "${after}" ]; then
    log "new commits ${before:0:7}..${after:0:7} — pushing"
    for attempt in 1 2 3 4; do
      if git push origin "${BRANCH}"; then log "push ok"; break; fi
      log "push failed (attempt ${attempt}); backing off"; sleep $((2 ** attempt))
    done
  else
    log "no new commits this cycle"
  fi

  if [ "${MAX_CYCLES}" -ne 0 ] && [ "${cycle}" -ge "${MAX_CYCLES}" ]; then
    log "reached MAX_CYCLES=${MAX_CYCLES}; exiting"; break
  fi
  log "sleeping ${INTERVAL}s"
  sleep "${INTERVAL}"
done
