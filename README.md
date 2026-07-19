# Nexus — Computational Capability Search (CCS)

Computer architecture asks: *what capabilities should new hardware provide?*

CCS asks the inverse: **what capabilities already exist in deployed hardware but remain hidden, because our software abstractions never search for them?**

A modern phone is a dense physical measurement instrument. Its battery current traces the thermal environment; its WiFi RSSI traces bodies moving through a room; its barometer traces doors and HVAC cycles. Nexus is an open, reproducible platform for systematically searching, falsifying, and cataloging these latent capabilities — including the negative results.

## Documents

| Document | Contents |
|---|---|
| [`docs/ccs-vision.md`](docs/ccs-vision.md) | The discipline: the latent capability space, the Prospecting Loop, certification by invariance, capability half-life, the composition algebra, the dual-use privacy audit. |
| [`docs/architecture.md`](docs/architecture.md) | The platform: synchronized logger, immutable archive, screening engine, experiment harness, capability registry, repository layout, week-1 build order. |

## Registry

| File | Contents |
|---|---|
| [`registry/capability.schema.json`](registry/capability.schema.json) | JSON Schema (draft 2020-12) for registry entries. |
| [`registry/examples/occupancy_v1.json`](registry/examples/occupancy_v1.json) | Example **positive** entry: room occupancy from WiFi + battery + thermal + IMU. |
| [`registry/examples/battery_light.json`](registry/examples/battery_light.json) | Example **negative** entry: a falsified claim, kept as a first-class result. |

## Status

Design phase. The logger, screening engine, harness, and registry validator are specified in [`docs/architecture.md`](docs/architecture.md) §7–8 and are the next build targets.
