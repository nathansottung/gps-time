# SPEC — RF Tasking Between Nodes, and the First FM TDOA Trial

## Status

OPTION, planned. Extends SPEC-RF-NODE-AND-TDOA.md. Built in stages; each stage stands on its own.

## Goal

Let nodes ask other nodes to capture the same signal at the same moment, so the coordinator can compare arrival times. Start with nodes owned by one operator, then open it, with consent, to third-party requests.

---

## 1. Capability registry

Each node publishes a small, signed capability record:

- node ID and owner-chosen display name
- **approximate location only** (rounded to a level the owner picks, e.g. ~1 km or ~10 km); exact surveyed position stays private unless the owner opts in
- SDR model, tunable frequency range, maximum sample rate and bandwidth
- frequency reference: free-running, calibrated, or GPS-disciplined
- timing state: PPS, NTP-synced (with current offset bound), or MLAT-calibrated
- **allowed bands**: the frequency ranges the owner permits others to request
- availability: open, owner only, or busy

The registry lives on the coordinator. Nodes refresh their record periodically; stale records are marked offline.

## 2. Capture task protocol

A capture task is a signed request:

- task ID, requester ID
- center frequency, bandwidth, sample rate
- **start time in UTC, a few seconds in the future**, and duration (short: typically under 1 s)
- purpose (free text, logged)
- what to return: IQ snippet, or correlation features only

Flow:

1. Requester sends the task to the coordinator.
2. Coordinator forwards it to matching nodes over a persistent connection (MQTT or WebSocket).
3. Each node checks it against its allowed bands, its own availability, and rate limits, then **accepts or declines**. Declines need no reason.
4. Accepting nodes tune ahead of time and capture at the scheduled UTC instant.
5. Nodes return results tagged with their timing quality and frequency reference state.
6. Coordinator correlates and solves; the result goes to the requester with uncertainty.

Every task and response is logged on the node, so owners can see what their receiver was asked to do.

## 3. Stages of access

- **Stage A — one owner:** only nodes owned by the same operator can task each other.
- **Stage B — trusted group:** owners add each other by key; tasks flow only between members.
- **Stage C — third parties:** any authenticated requester may task nodes that opt in, limited to each node's allowed bands, with per-requester rate limits. Owners can block requesters.

## 4. Rules

- Owners control their receivers: allowed bands, rate limits, and an off switch.
- Locate only broadcast stations, amateur transmissions, beacons, public aircraft broadcasts, and participating transmitters.
- Never decode or keep the content of private communications. Keep timing and signal metadata; IQ snippets are short and deleted after processing unless the owner keeps them.
- Every position result carries an error estimate. Never show a bare point.

---

## 5. First trial: FM broadcast TDOA

### Why FM

High power, always on, easy to receive with any SDR, and broadcast tower locations are public, which gives ground truth to check results against.

### Setup

- 2–3 identical or near-identical nodes (same SDR model, same software), spread several km apart with the target tower outside the line joining them.
- Each node synced to a GPS Time station by NTP, or with its own PPS.

### The timing problem, and the fix

NTP gives each node sub-millisecond time, but USB buffering adds ~1–10 ms of uncertainty to when a sample was actually received: far too much (1 ms ≈ 300 km).

Fix: use a **reference transmitter**.

1. Pick two FM stations whose towers are both public.
2. All nodes capture both stations in the same short window (switching quickly, or with enough bandwidth to hold both).
3. Using tower A's known position, compute the expected arrival-time difference at each node. The measured difference minus the expected one gives each node's clock offset.
4. Apply those offsets to tower B, solve its position, and compare it with its published location.

This is the same idea as ADS-B MLAT calibration, but simpler to start with.

### Expected accuracy (to be measured, not promised)

- An FM signal occupies ~200 kHz, so raw range resolution is about c / bandwidth ≈ 1.5 km; correlating the program audio content and interpolating between samples should improve this, perhaps to hundreds of meters.
- Multipath, node geometry, and drift between the two captures will limit it further.
- With 2 nodes the result is a hyperbola line; 3 nodes give a position; more nodes improve it.

### Success criteria

- The solved tower B position falls within the stated error ellipse of the published location.
- Repeat runs agree with each other.
- Report the error honestly, including failures.

### What comes after

If FM works: ADS-B MLAT calibration, then narrower signals and amateur fox hunts, then Stage B and C access.

## Open questions

- MQTT vs WebSocket for tasking.
- Signature scheme for tasks and capability records.
- Whether nodes switch between two FM stations or capture both in one wide window.
- How the coordinator is hosted for a small group without a mandatory cloud.
