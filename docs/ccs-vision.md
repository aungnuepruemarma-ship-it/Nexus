# Computational Capability Search (CCS)

**A discipline for discovering what deployed hardware can already do**

Version 0.1 — Vision & Formal Framing

---

## 1. The Inversion

Computer architecture asks a forward question:

> *What capabilities should new hardware provide?*

It answers by designing silicon, shipping it, and exposing it through stable abstractions: an accelerometer API, a battery-level API, a WiFi-scan API. Each abstraction names the capability the hardware was *designed* to have, and hides everything else.

CCS asks the inverse question:

> *What capabilities already exist in deployed hardware but remain hidden, because our software abstractions never search for them?*

The premise is that a modern phone is not a bundle of sensors — it is a **dense physical measurement instrument embedded in a room, a pocket, a building, a crowd**. Its battery current traces the thermal environment. Its WiFi RSSI traces the water-filled bodies moving between it and the access point. Its clock skew traces temperature. Its barometer traces elevators, doors, and HVAC cycles. None of these were designed as occupancy sensors, door sensors, or HVAC monitors — but the information is physically present in the signals, waiting for software that bothers to look.

Every such latent function is a capability that was **manufactured but never shipped**. Billions of instances of it are already deployed. CCS is the systematic search for them.

### Why "search" and not "invention"

Side-channel research, ubiquitous-computing papers, and clever hacks have found individual latent capabilities for decades — one paper, one trick, one device at a time. What has never existed is the *infrastructure of a search*: a shared coordinate system for the space being searched, a falsification standard for claims, a registry that accumulates results (including failures), and a way to compose verified findings into larger ones. Astronomy became a science when it stopped being anecdotes about bright objects and started being a catalog with coordinates. CCS proposes the same transition for latent hardware capability.

---

## 2. The Latent Capability Space

To search a space you must first define it.

### 2.1 Definitions

- **Signal**: any time-stamped physical observable a device exposes without hardware modification — IMU axes, battery telemetry, thermal zones, CPU counters, WiFi scan results, barometer, ambient light, and so on. Let `Σ` be the full signal set of a device class.
- **Task**: a question about the physical or contextual world with a defined ground truth — "how many people are in this room?", "which floor am I on?", "is the device on wood or concrete?".
- **Capability claim**: a falsifiable statement of the form

  > Task `T` is inferable from signal subset `S ⊆ Σ` on device population `D`,
  > at accuracy `A`, energy cost `E`, latency `L`, and privacy cost `P`.

A capability is not a model. A model is *evidence for* a capability claim. The claim is about physics and populations of devices; the model is one witness.

### 2.2 The space

The latent capability space is the lattice of signal subsets crossed with the task set:

```
CapSpace  =  𝒫(Σ) × Tasks
```

Each point is a candidate claim. The powerset structure matters because it gives the search *direction*:

- **Monotonicity of information**: adding signals never removes information (`S ⊆ S′` implies `I(S; T) ≤ I(S′; T)`), so if a subset fails an information screen, every subset of it fails too. Failed screens prune downward through the lattice.
- **Anti-monotonicity of cost**: energy and privacy cost grow with `|S|`, so the interesting frontier is the *minimal* subsets that still carry the information — the Pareto frontier of information vs. cost.

This is what makes CCS a search problem rather than a grab-bag: the space has an order, the order supports pruning, and the objective is a frontier, not a single optimum.

### 2.3 What counts as "found"

A point in CapSpace is a **discovered capability** only when the claim survives falsification (Section 4). Until then it is a *candidate*. A claim that is tested and fails becomes a **negative result** — and negative results are stored with the same care as positive ones, because they prune the lattice for every future searcher. A space this large is mapped as much by its dead ends as by its finds.

---

## 3. The Prospecting Loop

The v0.1 platform describes a linear pipeline (logger → archive → discovery → registry). CCS closes it into a loop, because capabilities are perishable (Section 5) and because every result — positive or negative — changes where the search should look next.

```
        ┌──────────────────────────────────────────────────┐
        │                                                  │
        ▼                                                  │
   1. SENSE ──► 2. SCREEN ──► 3. HYPOTHESIZE ──► 4. FALSIFY│
   (log all      (cheap MI     (candidate         (adversarial
    signals,      estimates     claims on the      cross-device
    one clock)    over the      Pareto frontier)   validation)
                  lattice)           │                 │
                                     │        pass ────┤──── fail
                                     │                 │       │
        ┌────────────────────────────┘                 ▼       ▼
        │                                        5. CERTIFY  NEGATIVE
        │                                        (registry    RESULT
        │                                         entry +    (registry
        │                                         privacy     entry)
        │                                         audit)        │
        │                                              │        │
        │                                              ▼        │
        │                                        6. COMPOSE     │
        │                                        (algebra of    │
        │                                         capabilities) │
        │                                              │        │
        └──────────── 7. DECAY-WATCH ◄─────────────────┴────────┘
                      (re-verify on OS/hardware drift;
                       expired claims re-enter the loop)
```

### Stage 1 — Sense

Record every accessible signal on **one monotonic timeline**, with zero interpretation. The logger is deliberately dumb: it records reality, it does not model it. (The full logger, archive format, and collection protocol are specified in [`architecture.md`](architecture.md).)

### Stage 2 — Screen (the novel gate)

Before any ML, estimate mutual information `I(S; T)` between candidate signal subsets and labeled tasks, using cheap non-parametric estimators over windowed features. This stage exists because model training is the expensive resource, and the lattice is exponential. Screening:

- prunes subsets with no measurable information gain over baseline (and, by monotonicity, everything below them);
- ranks survivors by estimated information per joule of sensing cost;
- turns "let's throw a neural net at everything" into a budgeted queue.

A subset that fails the screen is *recorded as screened-out*, with the estimator and threshold used — a weak negative result, cheaper than a full one, still worth keeping.

### Stage 3 — Hypothesize

Promote the top of the screened queue into explicit capability claims: task, signal subset, target accuracy, energy budget, device population. Every claim is written down *before* the validation run, pre-registration style, so results cannot be quietly redefined into successes.

### Stage 4 — Falsify

Train on one slice of the world; test on a deliberately hostile other slice. The standard is defined in Section 4. The point of this stage is to try to *kill* the claim, not to confirm it.

### Stage 5 — Certify

A surviving claim enters the registry with its full evidence: protocols, metrics, energy, latency, supported and unsupported devices, and a completed privacy audit (Section 6). Certification is versioned and dated, and carries an expiry.

### Stage 6 — Compose

Certified capabilities become inputs to new candidate claims via the composition algebra (Section 7). Composition points the search at regions of CapSpace no single-signal analysis would reach.

### Stage 7 — Decay-watch

Certified claims are periodically re-verified against new OS versions, new device revisions, and new environments. A claim that stops reproducing is not deleted — it transitions to `unstable` or `deprecated`, and its decay event is itself data (Section 5).

---

## 4. Certification by Invariance

The single most common failure mode in this research area is a model that has quietly memorized its room, its device, or its week. CCS therefore defines validity *as* invariance:

> A capability claim is certified only if it transfers across at least one axis of hardware population (OEM/model) **and** at least one axis of environment (room/building), with a bounded, reported accuracy drop.

Concretely, the falsification standard requires:

1. **Cross-OEM split** — train on devices from OEM set `𝒜`, test on disjoint OEM set `ℬ`. Never certify from a single manufacturer.
2. **Cross-environment split** — train in rooms `R₁…Rₖ`, test in rooms never seen in training. Never train and test in the same room.
3. **Baseline dominance** — the fused claim must beat the best *single-signal* baseline on the same split; otherwise the "fusion capability" is an illusion and the single signal is the real finding.
4. **Reproduction** — an independent re-run of the collection protocol (different operator, different day) must land within the claim's stated confidence interval.
5. **Budget compliance** — measured energy and latency within the pre-registered budget.

Failing any one of these produces a typed negative result: `environment-bound`, `oem-bound`, `redundant-with-baseline`, `non-reproducible`, or `over-budget`. The type matters — an `oem-bound` failure is a *conditional* capability worth keeping (works on Pixel, fails on Samsung → status `unstable`, scoped to its supported set), whereas `non-reproducible` is a true dead end.

---

## 5. Capability Half-Life

Designed capabilities are stable because vendors commit to their abstractions. Latent capabilities have no such contract — they live in the gap between the abstraction and the physics, and that gap moves every time an OS update changes a sensor batching policy, a kernel changes a thermal governor, or an OEM swaps a component supplier.

CCS treats this decay as a first-class, measurable property:

- Every certified capability carries a **`valid_until`** date and an estimated **`half_life`** — the expected time until re-verification fails, estimated from the capability's dependency surface (which OS subsystems, which hardware components) and from the observed decay of similar capabilities.
- The decay-watch stage schedules re-verification with frequency proportional to `1 / half_life`.
- Decay events are logged to the registry. Over time this yields something genuinely new: **an actuarial table for latent hardware capability** — which signal families are durable across the Android ecosystem, and which evaporate with every quarterly update. That table is itself a research output, and it feeds back into screening (durable signal families get priority).

A consumer of the registry never asks "does capability X exist?" but "is capability X's certification currently live?" — the same shift TLS made from *keys* to *certificates*.

---

## 6. The Dual-Use Audit

Every latent capability is, by construction, an inference the device's designers did not intend to expose. That is exactly the definition of a privacy side channel. CCS's position is that this cannot be an afterthought:

> **Certification requires an adversarial privacy audit, and its findings are published in the registry entry alongside the accuracy numbers.**

The audit asks, for the certified signal subset and model:

1. **Bystander inference** — what can this capability reveal about people who did not consent (occupants of a room, passers-by)?
2. **Granularity escalation** — could the same signals, with more effort, support a finer-grained inference (from "room occupied" toward "who is in the room")? The audit reports the escalation gradient, not just the current point.
3. **Permission surface** — which Android permission tier gates each signal in `S`? A capability built entirely from permissionless signals is flagged, because it is invisible to the user's consent model.
4. **Mitigations** — minimum sampling rate / quantization at which the intended inference survives but the escalated one degrades. Registries store the *mitigated* operating point as the recommended one.

The resulting `privacy` score in the registry is not a formality: capabilities whose audit shows unbounded escalation from permissionless signals are certified as **findings** (they are true, and the community should know) but flagged `disclosure-sensitive`, with the registry entry documenting the risk rather than shipping a turnkey recipe. CCS is a search for capability, and honest cartography includes marking the cliffs.

---

## 7. The Capability Algebra

The registry would be a filing cabinet if entries could not combine. CCS defines composition as a small algebra with explicit propagation rules, so that composite claims inherit — and cannot silently launder — the costs and uncertainties of their parts.

Every certified capability exposes the same interface:

```
Capability<T> := () → {
  estimate  : T,
  confidence: [0,1],
  energy    : mJ per invocation,
  latency   : ms,
  privacy   : audit score,
  valid_until, version
}
```

### Operators

| Operator | Form | Estimate | Confidence | Energy | valid_until |
|---|---|---|---|---|---|
| **Fusion** `⊕` | `A ⊕ B → C` (same task, different signals) | combined per fusion rule | may exceed max(A,B) — only if certified as beating both baselines | `E_A + E_B` (shared sensing deduplicated) | `min(A, B)` |
| **Refinement** `▷` | `A ▷ B → C` (B conditions on A's output) | B's estimate given A | `≤ conf(A) · conf(B)` upper bound; measured, never assumed | `E_A + E_B` | `min(A, B)` |
| **Temporal integration** `∫` | `∫ₜ A → C` (aggregate A over a window) | windowed statistic | grows with window per measured mixing rate | `n · E_A` | `A`'s |

Three rules keep the algebra honest:

1. **No free confidence.** A composite's confidence is a *claim*, and claims are certified the same way atoms are: the composite goes through Falsify (Section 4) itself. The algebra provides the upper bounds and the null hypothesis; measurement provides the number.
2. **Costs are conserved.** Energy, latency, and privacy cost only add (minus explicitly shared sensing). A composite that looks cheap is mis-accounted.
3. **Expiry propagates as `min`.** A tower of compositions is only as durable as its most perishable atom — and the registry can compute, for any composite, exactly which atomic re-verification failure would take it down (its *decay cut-set*).

The registry stores composites with `depends_on` edges, so the whole registry forms a DAG. When decay-watch expires an atom, every dependent composite is automatically demoted to `unstable` pending re-verification — capability supply chains, with the recall semantics that implies.

Example: `occupancy ⊕ floor → crowd_density_per_floor` — certified only after crowd-density itself passes cross-OEM, cross-building falsification, with energy = deduplicated sum and `valid_until = min(occupancy, floor)`.

---

## 8. What Success Looks Like

CCS is falsifiable at the program level, not just the claim level. It has succeeded if, after a year of operation:

1. **The registry is non-trivially populated in all four quadrants** — durable positives, typed negatives, unstable (OEM-scoped) findings, and decayed entries with recorded decay events. A registry with only positives means falsification isn't working.
2. **The screen predicts the outcome.** Mutual-information screening scores correlate with downstream certification success; if they don't, the search has no compass and Section 2's structure is decoration.
3. **At least one composite outperforms its atoms** under the full certification standard — evidence that the algebra finds regions of CapSpace that single-signal search cannot.
4. **The actuarial table says something.** Half-life estimates for at least a few signal families are grounded in observed decay events, not priors.
5. **Someone reproduces a registry entry from its protocol alone**, on hardware the original team never touched. This is the only success criterion that matters if the others all hold: the registry is a scientific instrument exactly to the degree that its entries transfer.

And it has *failed* — informatively — if the negatives dominate everywhere: if after honest search the latent capability space of commodity phones turns out to be mostly empty above the single-sensor baselines. That result would itself be worth publishing. A search discipline that cannot fail is not one.

---

## 9. Relationship to the v0.1 Platform

The Capability Discovery Platform v0.1 (logger, archive, experiment protocol, registry) is the **laboratory**; CCS is the **research program run inside it**. Every v0.1 component survives, with a sharpened role:

| v0.1 component | CCS role | What CCS adds |
|---|---|---|
| Synchronized logger | Stage 1 (Sense) | unchanged — dumb by design |
| Physical state archive | evidence store | immutability now serves *pre-registration*: claims reference archive hashes |
| Experiment protocol | Stages 3–4 | typed failure conditions; pre-registered budgets |
| Discovery engine | Stages 2–3 | MI screening gate before model search |
| Capability registry | Stages 5–7 | schema gains `valid_until`, `half_life`, `privacy_audit`, typed negative results, dependency DAG |

The concrete component specifications, schemas, and repository layout live in [`architecture.md`](architecture.md). The machine-readable registry schema lives in [`../registry/capability.schema.json`](../registry/capability.schema.json).
