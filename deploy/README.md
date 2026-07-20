# Hosting the Nexus discovery loop persistently

This session runs the daemon inside an **ephemeral container** — it stops when the container
is reclaimed. To keep the Automated Computer Scientist building and committing across reboots,
host it on a machine you control. Three ready-to-use options:

## 1. systemd (always-on daemon) — recommended for a workstation/server

The daemon self-schedules (5-min cadence, 280s per-run cap); systemd keeps it alive.

```bash
git clone <this repo> ~/nexus && cd ~/nexus
git checkout claude/capability-discovery-platform-0cti9v
pip install -r requirements.txt            # + requirements-dream.txt for the local LLM
cp deploy/nexus-dreamer.service ~/.config/systemd/user/
# edit paths in the unit if your checkout isn't ~/nexus, then:
loginctl enable-linger "$USER"
systemctl --user daemon-reload
systemctl --user enable --now nexus-dreamer
journalctl --user -u nexus-dreamer -f
```

## 2. systemd timer (scheduler-driven, one cycle per tick)

Prefer a tick over a resident process? Use the timer + oneshot service (default every 5 min;
edit `OnUnitActiveSec=1h` for hourly):

```bash
cp deploy/nexus-dreamer.timer deploy/nexus-dreamer-oneshot.service ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now nexus-dreamer.timer
systemctl --user list-timers | grep nexus
```

## 3. cron (every 5 minutes)

```bash
crontab -e     # paste deploy/nexus-dreamer.cron, edit paths
```

## Requirements on the host

- **git auth must be non-interactive** (SSH key loaded in the agent, or a credential helper /
  PAT) — the loop pushes on its own. Test `git push` once by hand first.
- Python deps: `requirements.txt` (core) and, for the local model, `requirements-dream.txt`
  (`transformers`, CPU `torch`, `huggingface_hub`). Without them the loop still runs with
  `--no-model` (heuristic hypotheses).
- **Don't-sleep:** the daemon already re-execs under `caffeinate` (macOS) or `systemd-inhibit`
  (Linux) and runs `xset s off -dpms` when a display is present. A always-on server usually
  needs none of this.

## What "keeps building" means honestly

Once every backlog law is certified the loop **no-ops** until either a law's dated
certification lapses (decay → it re-verifies and re-commits) or a new `Dream` + `experiments/`
module is added (then it discovers and commits it next tick). It is a maintainer of a live,
honest registry — not an infinite generator of brand-new physics.
