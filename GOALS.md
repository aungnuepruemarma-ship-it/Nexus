# Nexus Mission — the goal the machine pursues on its own

> Discover the hidden **laws of this machine** — measurable, reproducible facts about its
> CPU, memory, cache, clock and OS that no spec sheet states — hypothesize each, let it be
> measured on real hardware, certify only what survives falsification, and keep building and
> committing new laws to the registry, **forever**.

This mission is encoded as `ccs.dream.engine.MISSION` and framed into the local model's system
prompt on every cycle, so each hypothesis the model proposes is in service of it. The
`DreamEngine` pursues it autonomously: hypothesis → real experiment → falsification → registry
→ git commit, driven by `scripts/dream_daemon.sh` on a 5-minute cycle.

## How the machine keeps building toward the goal

1. **Backlog** — `ccs.dream.engine.default_backlog()` lists the pending laws. The loop works
   through whatever is not yet certified (or whose dated certification has lapsed).
2. **Growth** — a human (or a future generative step) adds a new `Dream` + its `experiments/`
   module; the daemon discovers and commits it automatically on the next cycle.
3. **Decay** — positive laws carry a `valid_until`; when one lapses the daemon re-verifies and
   re-commits it, so the registry stays true over time rather than going stale.

## Laws discovered so far (autonomous commits)

| law | what it recovers |
|---|---|
| `timer_resolution_v1` | effective clock granularity |
| `mem_bandwidth_v1` | sustained streaming memory bandwidth |
| `syscall_latency_v1` | user→kernel round-trip cost |
| `flops_throughput_v1` | sustained floating-point throughput |
| `memory_access_penalty_v1` | random-vs-sequential access penalty (cache line + prefetcher) |

Plus the curated capabilities in `results/REPORT.md` (entropy source, contention sensor,
memory-hierarchy ladder, and the honest negatives).

## Running the goal

```bash
bash scripts/dream_daemon.sh          # pursue the mission: every 5 min, 280s cap, auto-commit + push
python scripts/dream_loop.py          # one pass over the pending backlog
```

The daemon keeps the *loop* awake. It cannot keep a physical monitor awake — on a headless
host there is no desktop session; on a workstation, wrap it with `caffeinate` (macOS) or
`systemd-inhibit` / `xset s off` (Linux) where the screen actually is.
