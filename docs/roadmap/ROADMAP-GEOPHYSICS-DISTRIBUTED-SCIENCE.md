# ROADMAP — Geophysics and Distributed Science

## Status

FUTURE. Research track. Starts after v1.4.0 and the oscillator profile.

## Goal

Use a network of precisely timed, fixed GNSS stations to measure real geophysical effects, with honest limits on what each hardware tier can detect.

## What the current hardware can and cannot do

The u-blox MAX-M8Q is a single-frequency receiver giving code-based positions. Averaging narrows the mean position to decimeters, but not to the millimeters most geophysics needs. Station clocks are disciplined to GPS, so they are not independent references.

**Not feasible, at any tier in this project:**

- Earth's gravity field or mass from clock comparisons. Gravitational time dilation is about 1 × 10⁻¹⁶ per meter of height; that needs optical clocks far beyond GPS-disciplined crystals.
- Earth's mass from station data. It is already known from satellite orbits, and GPS depends on that value.

The project must never claim these.

## Tier 1 — current hardware (single-frequency)

1. **GNSS interference mapping.** Compare C/N₀ drops and fix losses across stations to map regional interference. Report observations, never causes.
2. **Lightning and transient timing.** Time-of-arrival of VLF sferics or other impulses across stations (with RF nodes).
3. **Space weather context.** Show Kp index and solar flare data (external) beside GNSS signal health.
4. **Long-term site stability.** Track the averaged position over months; detect antenna or mount changes.

## Tier 2 — dual-frequency receivers (e.g. u-blox ZED-F9P)

Dual-frequency carrier-phase data with precise point positioning (PPP) or a reference network reaches centimeter level, which opens:

1. **Solid Earth tides.** The ground rises and falls by roughly 30 cm twice daily. Fit observed vertical motion against the tide model.
2. **Ionosphere mapping.** Total electron content (TEC) per station from the two frequencies; network maps; travelling disturbances from storms, earthquakes, and rocket launches.
3. **Tropospheric water vapor.** Zenith wet delay converts to precipitable water, a value used in weather forecasting.
4. **Crustal motion.** Velocities over years at mm/yr scale need long, careful records; treat as a long-term goal.
5. **Scintillation monitoring** where receivers report it.

All Tier 2 outputs are **modeled**, carry uncertainties, and state the processing method and reference data used.

## Network design

- Stations publish signed, timestamped observation summaries to an optional coordinator. No mandatory cloud.
- Raw data stays on stations by default; operators opt in to sharing.
- Station positions follow each operator's privacy mode. Science products for public release use rounded positions unless the operator consents.
- Heavy processing (PPP, network solutions, maps) runs on the coordinator tier.

## Validation

- Compare results with public references: IGS products, NOAA CORS stations, published TEC maps, and tide models.
- Publish method notes with every product.

## Open questions

- Which PPP software to use (e.g. RTKLIB, open-source PPP tools).
- Data format for sharing (RINEX for raw observations).
- Licensing of shared data.
