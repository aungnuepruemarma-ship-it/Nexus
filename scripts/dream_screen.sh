#!/usr/bin/env bash
# Launch the discovery daemon inside a detached tmux (preferred) or screen session, so it
# keeps running after you log out. Reattach any time to watch it think.
#
#   bash scripts/dream_screen.sh            # start detached (tmux 'dream' or screen 'dream')
#   tmux attach -t dream     # or:  screen -r dream        # reattach
#   tmux kill-session -t dream                              # stop
#
# The daemon itself handles the 5-min cadence, 280s per-run cap, heartbeat, and recovery.
set -u
cd "$(dirname "$0")/.." || exit 1
SESSION="${DREAM_SESSION:-dream}"

if command -v tmux >/dev/null 2>&1; then
  if tmux has-session -t "$SESSION" 2>/dev/null; then
    echo "tmux session '$SESSION' already running — attach with: tmux attach -t $SESSION"; exit 0
  fi
  tmux new-session -d -s "$SESSION" "bash scripts/dream_daemon.sh"
  echo "started daemon in tmux session '$SESSION'. Attach: tmux attach -t $SESSION"
elif command -v screen >/dev/null 2>&1; then
  screen -dmS "$SESSION" bash scripts/dream_daemon.sh
  echo "started daemon in screen session '$SESSION'. Reattach: screen -r $SESSION"
else
  echo "neither tmux nor screen found; falling back to nohup"
  nohup bash scripts/dream_daemon.sh > results/dream_daemon.log 2>&1 &
  echo "started daemon via nohup (PID $!). Log: results/dream_daemon.log"
fi
