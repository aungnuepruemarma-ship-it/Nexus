"""Physics-flavored room-occupancy simulator.

Generates windowed features (not raw signals, for speed) for several device OEMs in
several rooms under several conditions. Occupancy in {0,1,2,3+} genuinely modulates:

  * ``wifi_rssi``  — bodies attenuate/scatter the link: RSSI variance rises with people;
  * ``thermal``    — body heat lifts skin/battery temperature slightly;
  * ``imu``        — footstep micro-vibration raises accel band energy.

These couplings are calibrated the SAME way across devices and rooms (with per-device
gain and per-room offset noise), so a real capability transfers. A planted trap signal
``room_echo`` encodes room identity strongly and occupancy weakly: it scores high MI in
pooled data but must fail cross-room transfer. The trap exists to prove the falsifier
rejects memorization.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from ..signals import FeatureSet

OEMS = ("Pixel", "Samsung", "Xiaomi")
ROOMS = ("office", "bedroom", "conference")
CONDITIONS = ("morning_ac", "night_noac")
CLASSES = (0, 1, 2, 3)  # 3 == "3+"

# Per-device sensor gain (manufacturing variation) and per-room ambient offset.
# Gains are close (real occupancy features are chosen to be gain-robust) so the
# cross-device domain shift is realistic rather than pathological.
_DEVICE_GAIN = {"Pixel": 1.0, "Samsung": 0.97, "Xiaomi": 1.03}
_ROOM_OFFSET = {"office": 0.0, "bedroom": 0.3, "conference": -0.2}


@dataclass
class SimConfig:
    windows_per_cell: int = 40      # windows per (oem, room, condition, occupancy)
    seed: int = 7
    include_trap: bool = True
    noise: float = 0.5


def _cell_features(rng, oem, room, occ, cfg: SimConfig):
    """Each signal is individually *weak* (per-person step comparable to its noise),
    with independent noise across signals, so no single signal certifies but their
    fusion does. This is the realistic regime the baseline-dominance rule rewards."""
    n = cfg.windows_per_cell
    g = _DEVICE_GAIN[oem]
    off = _ROOM_OFFSET[room]
    people = occ
    s = cfg.noise

    # wifi_rssi variance rises with people; step ~1.4, independent noise ~1.5
    rssi_var = g * (2.0 + 1.4 * people) + rng.normal(0, 1.5 * s, n) + 0.2 * off
    rssi_mean = -50 - 1.2 * people * g + rng.normal(0, 1.5 * s, n)

    # thermal: body heat lifts temperature; step ~1.1, independent noise ~1.4
    thermal = g * (24.0 + 1.1 * people) + 0.5 * off + rng.normal(0, 1.4 * s, n)

    # imu: footstep band energy; step ~1.0, independent noise ~1.3
    imu = g * (1.0 * people) + rng.normal(0, 1.3 * s, n)

    cols = {
        "wifi_rssi.0.var": rssi_var,
        "wifi_rssi.0.mean": rssi_mean,
        "thermal.0.mean": thermal,
        "imu.0.bandenergy": imu,
    }
    if cfg.include_trap:
        # room_echo: strong room code + weak occupancy + noise -> memorization trap
        room_id = ROOMS.index(room)
        cols["room_echo.0.mean"] = 10.0 * room_id + people + rng.normal(0, 0.15, n)
    return cols, n


def generate(cfg: SimConfig | None = None):
    """Return (FeatureSet, y, oem_groups, room_groups, signal_cost_mj)."""
    cfg = cfg or SimConfig()
    rng = np.random.default_rng(cfg.seed)

    feat_names = ["wifi_rssi.0.var", "wifi_rssi.0.mean", "thermal.0.mean", "imu.0.bandenergy"]
    feat_signal = ["wifi_rssi", "wifi_rssi", "thermal", "imu"]
    if cfg.include_trap:
        feat_names.append("room_echo.0.mean")
        feat_signal.append("room_echo")

    rows, ys, oems, rooms = [], [], [], []
    for oem in OEMS:
        for room in ROOMS:
            for cond in CONDITIONS:
                for occ in CLASSES:
                    cols, n = _cell_features(rng, oem, room, occ, cfg)
                    block = np.column_stack([cols[name] for name in feat_names])
                    rows.append(block)
                    ys.extend([occ] * n)
                    oems.extend([oem] * n)
                    rooms.extend([room] * n)
    X = np.vstack(rows)
    t_ns = np.arange(X.shape[0], dtype=np.int64) * 1_000_000
    fs = FeatureSet(X=X, names=feat_names, t_ns=t_ns, feature_signal=feat_signal)

    signal_cost_mj = {"wifi_rssi": 8.0, "thermal": 1.0, "imu": 3.0, "room_echo": 1.0}
    return fs, np.array(ys), np.array(oems), np.array(rooms), signal_cost_mj
