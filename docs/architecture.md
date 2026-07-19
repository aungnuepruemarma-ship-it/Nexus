# CCS Platform Architecture

Concrete system specification for the Computational Capability Search platform. The conceptual framing — the capability space, the Prospecting Loop, certification by invariance, capability half-life, the composition algebra, and the dual-use audit — is defined in [`ccs-vision.md`](ccs-vision.md). This document specifies the components that implement it.

---

## 1. System Layers

```
Android Device
      │
      ▼
Synchronized Logger          (Prospecting Loop stage 1: Sense)
      │
      ▼
Physical State Archive       (immutable evidence store)
      │
      ▼
Screening Engine             (stage 2: MI estimates over the signal lattice)
      │
      ▼
Experiment Harness           (stages 3–4: pre-registered claims, falsification)
      │
      ▼
Capability Registry          (stages 5–7: certification, composition DAG,
      │                       decay-watch scheduling)
      ▼
Applications / Research
```

---

## 2. Synchronized Logger (Android)

The logger records reality and performs **no ML and no interpretation**.

### Modules

```
Logger
├── Sensor Manager        (IMU, light, pressure)
├── WiFi Manager          (scans, RSSI, connection state)
├── Battery Manager       (voltage, current, temp, charge counter, status, health)
├── Thermal Manager       (CPU/battery/skin temps, throttling state, severity)
├── CPU Manager           (frequency, governor, utilization, idle, load, cores online)
├── Memory Manager        (available, cached, swap, pressure)
├── Device Metadata       (OEM, model, Android version, kernel, sensor inventory)
├── Event Marker          (operator-tagged ground-truth events)
├── Clock Synchronizer    (single monotonic timeline)
└── Storage Writer        (Parquet, append-only)
```

### Signals and default sampling

| Family | Signals | Rate |
|---|---|---|
| IMU | accelerometer, gyroscope, magnetometer, rotation vector, gravity, linear acceleration | 50 / 100 / 200 Hz (per-experiment) |
| Battery | voltage, current, temperature, capacity, charge counter, status, health | 1 Hz |
| Thermal | CPU temp, battery temp, skin temp, throttling state, severity | 1 Hz |
| CPU | frequency, governor, utilization, idle time, load average, core online/offline | 1 Hz |
| Memory | available RAM, cached RAM, swap, pressure | 1 Hz |
| Network | WiFi scan (SSID, BSSID, RSSI, channel, frequency, scan timestamp), connection state | every 5 s |
| Light | ambient light | 10 Hz |
| Pressure | barometer | 10 Hz |

### Timeline

- Every sample carries `timestamp_ns` from the **monotonic clock**. Never wall clock.
- One wall-clock ↔ monotonic anchor pair is recorded at session start (and on any clock event) in session metadata, so archives remain alignable across devices without polluting sample timestamps.

### Event markers

Operator-tagged ground truth, stored on the same timeline: `occupancy_start`, `occupancy_end`, `surface_changed`, `phone_picked_up`, `walking`, `sitting`, `room_changed`, `experiment_start`, `experiment_end`. Markers are the label stream for screening and falsification; they get the same immutability guarantees as sensor data.

---

## 3. Physical State Archive

**Immutable, append-only. Never edit data.** Claims in the registry cite archive content by hash; editing the archive would silently invalidate certifications.

### Layout

```
archive/
  device_A/
    session_001/
      imu.parquet
      wifi.parquet
      battery.parquet
      thermal.parquet
      cpu.parquet
      memory.parquet
      light.parquet
      pressure.parquet
      events.parquet
      metadata.json
```

### `metadata.json`

```json
{
  "device_id": "device_A",
  "oem": "Google",
  "model": "Pixel 8",
  "android": "15",
  "kernel": "6.1.x",
  "room": "office-2F-east",
  "ambient_temperature_c": 24.5,
  "experiment": "EXP-001",
  "operator": "anon-op-3",
  "sampling_rates": { "imu_hz": 100, "battery_hz": 1, "wifi_period_s": 5 },
  "clock_anchor": { "monotonic_ns": 0, "wall_utc": "2026-07-19T09:00:00Z" },
  "hash": "sha256:..."
}
```

`hash` covers the session's Parquet files; registry entries reference sessions by this hash (pre-registration linkage — see vision §3, stage 3).

Storage format is Parquet by default; SQLite or HDF5 are acceptable where Parquet tooling is unavailable, provided the schema and hashing rules are identical.

---

## 4. Screening Engine

Sits between the archive and the experiment harness (vision §3, stage 2).

- Extracts windowed features per signal family (configurable window, e.g. 10 s).
- Estimates mutual information `I(S; T)` between signal-subset features and event-marker labels with non-parametric estimators (k-NN / binned; estimator identity is recorded with the score).
- Walks the signal-subset lattice with monotonic pruning: a subset below threshold prunes all its subsets.
- Emits a ranked candidate queue: `(task, signal_subset, MI_estimate, sensing_cost_mJ, MI_per_mJ)`.
- Screened-out subsets are written to the registry as weak negatives (`status: negative`, `failure_type: screened-out`).

---

## 5. Experiment Harness

Implements pre-registration and falsification (vision §3–4). Every experiment follows the identical structure:

```
Hypothesis → Protocol → Collection → Discovery → Validation → Registry
```

### Experiment header (pre-registered before collection)

| Field | Example (EXP-001) |
|---|---|
| Experiment ID | `EXP-001` |
| Title | Room Occupancy |
| Question | Can occupancy be inferred from low-intrusion signals? |
| Ground truth classes | 0 / 1 / 2 / 3+ people |
| Target accuracy | pre-registered, e.g. ≥ 85% |
| Energy budget | pre-registered, e.g. ≤ 15 mJ per inference |
| Hardware | ≥ 3 phones, ≥ 3 OEMs (e.g. Pixel, Samsung, Xiaomi) |
| Rooms | office, bedroom, conference room |
| Conditions | morning/night × AC/no-AC × door open/closed |

### Collection protocol (EXP-001 reference)

```
5 min empty → 5 min one person → 5 min two people → 5 min empty → repeat
```

Sampling: WiFi 5 s · battery 1 Hz · thermal 1 Hz · IMU 100 Hz · light 10 Hz.

### Validation splits (certification by invariance — vision §4)

- **Train**: OEM set 𝒜, rooms R₁–R₂.
- **Test**: OEM set ℬ (disjoint), room R₃ (unseen).
- Never train and test in the same room. Never certify from one OEM.

### Baselines

WiFi-only, thermal-only, battery-only, IMU-only, manual fusion. The candidate must beat the best single-signal baseline on the *same* split.

### Metrics

Accuracy, precision, recall, F1, ROC-AUC, energy (mJ/inference), latency (ms), cross-device accuracy drop, privacy score (from the audit).

### Typed failure conditions

A claim fails certification — and is recorded as a typed negative — if any hold:

| `failure_type` | Condition |
|---|---|
| `redundant-with-baseline` | does not beat best single-signal baseline |
| `non-reproducible` | independent re-run outside stated CI |
| `oem-bound` | fails cross-OEM split (may be re-scoped to `unstable` with a supported-device list) |
| `environment-bound` | fails cross-room split |
| `over-budget` | energy or latency exceeds pre-registered budget |
| `screened-out` | eliminated at the MI screen (weak negative) |

---

## 6. Capability Registry

Stores validated knowledge — **including failures** — as a dependency DAG. Machine-readable schema: [`../registry/capability.schema.json`](../registry/capability.schema.json). Examples: [`../registry/examples/`](../registry/examples/).

### Entry schema (summary)

Core identity: `id`, `name`, `version`, `status`, `description`, `task`, `signals`, `model`.

Evidence: `accuracy`, `confidence`, `energy_mj`, `latency_ms`, `generalization` (per-OEM results), `supported_devices`, `unsupported_devices`, `training_protocol`, `validation_protocol`, `reproducibility`, `provenance` (archive session hashes), `references`.

CCS extensions: `valid_until`, `half_life_days`, `privacy_audit` (bystander inference, escalation gradient, permission surface, mitigations, `disclosure_sensitive` flag), `failure_type` (for negatives), `depends_on` + `composition_operator` (for composites), `limitations`, `failure_modes`, `date_created`, `last_verified`.

### Status lifecycle

```
experimental ──certify──► positive ──decay-watch fail──► unstable ──► deprecated
     │                                                      ▲
     └────falsify fail──► negative                          │
                                        dependency expired ─┘  (composites)
```

- `positive` — certified, live (`last_verified` within `valid_until`).
- `negative` — falsified, with `failure_type`. Permanent and citable.
- `unstable` — holds only on a scoped device population (e.g. works on Pixel, fails on Samsung), or pending re-verification after a dependency expired.
- `deprecated` — decayed and not worth re-certifying (e.g. broken after an Android release).
- `experimental` — pre-registered, not yet through falsification.

### Capability interface (runtime)

```
Capability<T> {
  estimate,     // T
  confidence,   // [0,1]
  energy,       // mJ
  latency,      // ms
  privacy,      // audit score
  valid_until,
  version
}
```

Example: `occupancy() → { estimate: 2, confidence: 0.92, energy: 11mJ, latency: 18ms }`.

### Composition

Composites are ordinary entries with `depends_on` and a `composition_operator` (`fusion`, `refinement`, `temporal-integration`). Propagation rules (energy additive, expiry = min, confidence measured not assumed) are normative in vision §7. The registry validator recomputes `valid_until` for composites and demotes dependents to `unstable` when an atom expires.

---

## 7. Repository Layout

```
Nexus/
  docs/
    ccs-vision.md          # discipline & formal framing
    architecture.md        # this document
  android/
    logger/                # logger app (planned)
  archive/
    schema/                # Parquet column schemas + metadata.json spec (planned)
  registry/
    capability.schema.json # machine-readable entry schema
    examples/              # example entries (positive + negative)
    registry.json          # the registry itself (planned; starts empty)
    validator.py           # schema + DAG validator (planned)
  discovery/
    features/  screening/  models/        # (planned)
  experiments/
    occupancy/  surface/  floor/  context/  # (planned)
  benchmark/
    capabilitynet/         # cross-device benchmark suite (planned)
  scripts/
    collect.py  validate.py  evaluate.py   # (planned)
  results/
```

## 8. Week-1 Deliverables (build order)

1. Design specification — these two documents. ✅
2. Registry schema + example entries — [`registry/`](../registry/). ✅
3. Android logger collecting synchronized signals to Parquet.
4. Archive schema + session hashing.
5. Experiment harness skeleton: pre-registration file format, split generator, baseline metrics.
6. Registry validator (`registry/validator.py`): schema check + DAG/expiry propagation.
7. One end-to-end collection session (EXP-001 protocol) to verify the pipeline.
