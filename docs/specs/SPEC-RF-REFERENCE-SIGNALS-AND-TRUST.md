# SPEC — Reference Signal Catalog and Trusted Node Cluster

## Status

OPTION, planned. Extends SPEC-RF-TASKING-AND-FM-TDOA-TRIAL.md. Each reference type is a separate, optional module.

## Goal

1. A catalog of signals with **known transmitter positions** (or self-reported positions) that a typical RTL-SDR can receive, used to calibrate node clock offsets and check results against ground truth.
2. A way for new nodes to earn trust by passing checks against those references and against already-trusted nodes, forming a local cluster of calibrated receivers.

---

## 1. Receiver baseline

Target hardware: RTL-SDR-class (e.g. RTL-SDR Blog V4).

- Normal range: about 24 MHz – 1.7 GHz.
- Below 24 MHz (AM broadcast, HF): only via direct sampling or an upconverter, with lower performance. Mark these modules **requires HF capability**.
- Max stable sample rate about 2.4 MS/s, which caps usable bandwidth.

Raw range resolution ≈ c / signal bandwidth. Wider signals give finer timing.

## 2. Reference signal catalog

| Signal | Frequency | Bandwidth | Position source | Best use | Notes |
|---|---|---|---|---|---|
| **ATSC digital TV** | 54–608 MHz (US) | ~6 MHz (SDR sees ~2.4 MHz of it) | FCC licence database | **Best TDOA reference**: wide, strong, constant, fixed towers | Pilot and sync segments are known patterns; good correlation |
| **FM broadcast** | 88–108 MHz | ~200 kHz | FCC licence database | First trial; easy | Content-dependent correlation; coarser |
| **NOAA Weather Radio** | 162.400–162.550 MHz | ~12.5 kHz | NOAA transmitter list | Presence and frequency calibration | Narrow: poor ranging, useful as a known-tower sanity check |
| **ADS-B** | 1090 MHz | ~2 MHz pulses | **Self-reported** by aircraft | MLAT calibration (proven method) | Aircraft positions can be wrong; use many and reject outliers |
| **AIS (ships)** | 161.975 / 162.025 MHz | ~25 kHz | **Self-reported** by ships | Calibration near coasts | Only useful near water |
| **Radiosondes** | ~400–406 MHz | narrow | **Self-reported** (GPS on balloon) | Opportunistic checks | Twice-daily launches |
| **WWV / WWVH** | 2.5, 5, 10, 15, 20 MHz | narrow | Fixed, published (Fort Collins, Kauai) | **Time and frequency check, not TDOA** | Skywave path delay varies by ms; requires HF capability |
| **AM broadcast** | 530–1700 kHz | ~10 kHz | FCC licence database | Ground-wave stability check | Very coarse ranging; requires HF capability |
| **Cellular sync signals (LTE)** | bands under 1.7 GHz | 1.4–20 MHz | Public tower databases (accuracy varies) | Later option | Use only broadcast sync/ID signals; never decode user traffic |

Rules for every entry:

- Store transmitter positions with their **source and date**; FCC/NOAA records can be wrong or out of date.
- Self-reported positions (ADS-B, AIS, radiosondes) are labeled **external** and checked for consistency before use.
- Never decode or store content of private communications. Broadcast program content may be correlated but not stored beyond the short capture.

## 3. Calibration checks ("parity checks")

For a node and a reference transmitter with a known position:

1. Compute the expected propagation delay from the node's position to the transmitter.
2. Capture the signal at a scheduled UTC instant, together with other nodes.
3. Compare measured arrival-time differences with expected ones.
4. The residual gives the node's clock offset (and, over time, its drift).

A check **passes** when residuals across several references agree within a set bound. A single reference never passes a node on its own.

## 4. Trusted cluster

### Anchor

The first node with PPS timing and a long position survey (the GPS Time station) is the **anchor**. Its position and timing quality are recorded with uncertainties.

### Joining

A new node:

1. Publishes its capability record (approximate location, SDR, timing state).
2. Runs calibration checks against at least two independent reference types (e.g. ATSC + ADS-B).
3. Runs peer checks: its solved offsets must agree with those of trusted nodes capturing the same signals.
4. If both pass, it becomes **trusted** with a score that reflects how many references and peers agree.

### Ongoing

- Trust is re-checked continuously; a node whose residuals drift out of bound is demoted.
- Each node's calibration records **which references and peers it relied on**, so errors can be traced.
- Error grows with each hop from the anchor; the coordinator tracks hop count and prefers direct reference checks over chained ones.
- Disagreement between nodes is reported as disagreement, never as a cause.

### Bad or dishonest nodes

- A node's results are never accepted on its own word; peers must corroborate.
- Results that contradict known transmitter positions or trusted peers lower its score.
- Owners can remove a node from their trusted group at any time.

## 5. Privacy

- Nodes share approximate location by default. Exact positions are used only inside the coordinator for solving, and only with the owner's consent.
- Calibration and trust records do not expose exact positions to other members.

## 6. Order of work

1. FM two-tower trial (existing spec).
2. ATSC as the main reference.
3. ADS-B MLAT calibration.
4. Trust scoring with the anchor plus one or two more nodes.
5. NOAA, AIS and radiosonde modules.
6. HF modules (WWV, AM) for nodes with HF capability.
7. Third-party access (Stage C).

## Open questions

- Which ATSC sync features correlate best within 2.4 MS/s.
- How to weight self-reported positions against licensed ones.
- Trust score formula and thresholds.
