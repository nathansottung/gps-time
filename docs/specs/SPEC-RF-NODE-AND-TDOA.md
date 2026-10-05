# SPEC — RF Node, MLAT Calibration, and Distributed TDOA

## Status

PLANNED. Builds on ROADMAP-SDR-RF-OBSERVATORY.md. Starts after v1.4.0.

## Goal

Separate RF nodes, each an SDR on its own machine, synced to a GPS Time station. Together they calibrate their timing against known signals, then locate other transmitters by time difference of arrival (TDOA). Main use: distributed amateur radio fox hunts.

## Architecture

- **RF node** (`rf-node/` in this repo): SDR, chrony client of the station, SoapySDR, OpenWebRX for listening, GNU Radio for measurement, and a small agent.
- **Agent:** records short IQ snippets around detections, tags each with UTC, the node's chrony offset and uncertainty, and its frequency reference state, then sends events to the coordinator.
- **Coordinator:** a stronger machine (not the station Pi) that runs calibration and position solving. Offline-capable; no cloud.
- **Shared event format** with the station's existing event model.

## Accuracy model

Position error ≈ c × timing error × geometry factor (GDOP). About 300 m per µs.

| Timing source | Typical error | Position error |
|---|---|---|
| Host clock + USB timestamps | ~1–10 ms | hundreds of km — not usable |
| Reference-signal calibration (MLAT) | ~50–200 ns | ~15–60 m |
| GPSDO-locked SDRs + calibration | ~10–50 ns | ~3–15 m |

Other limits, reported with every fix:

- **Bandwidth:** raw range resolution ≈ c / bandwidth (2 MHz ≈ 150 m); sub-sample correlation improves this, but not without limit.
- **Multipath:** reflections bias arrival times, worst in towns and indoors.
- **Geometry:** nodes surrounding the target give far better results than nodes in a line.
- **Frequency drift** between nodes during long captures.

Meter-level results are a stretch goal, not a promise.

## Phase 1 — MLAT calibration ("training")

- Every node listens to ADS-B at 1090 MHz. Aircraft broadcast their own positions, so expected arrival times at each node are known.
- The coordinator solves each node's clock offset and drift continuously from these shared signals, as public ADS-B MLAT networks do.
- Output per node: offset, drift, residual error, and a calibration quality score, labeled **modeled**.
- Node positions come from each node's own GNSS survey, at the privacy level its owner sets.

## Phase 2 — TDOA on other signals

- Apply the calibrated offsets to other captures: a target signal heard by three or more nodes gives a position estimate; two give a hyperbola line.
- Results show an error ellipse and the number of nodes used, labeled **modeled**. Never show a single point without its uncertainty.
- Optional: a known beacon at a surveyed spot to check accuracy continuously.

## Phase 3 — Distributed fox hunts

- A hunt mode: pick a frequency, nodes capture, the coordinator shows a live map of estimates and error ellipses.
- History of fixes so hunters see the estimate tighten over time.

## Rules and limits

- Locate only amateur radio transmissions, beacons, aircraft broadcasts meant to be public, and transmitters whose operators take part (such as fox hunt transmitters).
- Do not decode or store the content of private communications. Store timing and signal metadata, not audio, except for amateur signals the operator chooses to record.
- Never present a position as more certain than the error estimate supports.
- Follow the station's privacy modes for node positions.

## Open questions

- Which SDR and GPSDO to standardize on.
- How nodes discover and authenticate to the coordinator.
- Map tiles offline vs. none.
