# ADR-0006: Desktop app is a tray app running the Python backend, not Electron

**Status:** Accepted (owner decision, 2026-10-21). Applies to the future desktop app in `roadmap/ROADMAP-DESKTOP-FIELD-APP.md`; nothing is built yet.

## Context

The desktop field app roadmap planned an Electron app that reused the `web/` UI through a desktop data adapter, and left open whether to bundle the Python backend or port the timing logic to TypeScript. The desktop host notes (2026-10-21) proposed running the same backend and UI as the Pi from a tray app.

## Decision

- **No Electron.** A small tray app runs the station's Python backend on localhost and opens the UI in the default browser.
- **Packaged per OS** (Windows, macOS, Linux), for example with PyInstaller.
- **One backend:** the timing chain, PPS state machine and event logic are not ported to TypeScript. The `web/` UI is served by the same backend and API as on the Pi.

## Consequences

- One code path for timing semantics, provenance labels and privacy rules on the Pi and the desktop.
- No bundled Chromium; the UI depends on the user's browser, as on the Pi.
- Serial input moves to the Python side (e.g. `pyserial`) instead of Node `serialport`.
- Setting the system clock still needs a separate privileged helper per OS; neither the tray app nor the browser UI runs elevated.
- Open: the packager and installer format per OS, the tray library, and localhost port handling.
