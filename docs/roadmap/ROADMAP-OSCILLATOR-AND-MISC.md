# ROADMAP — Oscillator Profile, Networked SDR, Assisted Deploys, Evidence Capture

## Status

FUTURE. Ordered roughly by value. None blocks v1.4.0.

---

## 1. Trained oscillator profile (portable per board)

Learn how this Pi's crystal behaves so holdover estimates are based on measurement, not a single current-frequency guess.

- Record chrony's frequency estimate, skew, and CPU/board temperature over days to weeks while PPS is locked.
- Fit a model: frequency vs temperature, plus slow aging trend. Store fit quality and the data span it covers.
- Use it for holdover projections, labeled **modeled**, shown beside the simple projection.
- **Export/import** as one JSON file so the model survives a reflash.
- **Board binding:** the profile records a hash of the Pi's hardware serial (from `/sys/firmware/devicetree/base/serial-number`), never the raw serial. On import, the station compares hashes:
  - match: load and use;
  - mismatch: warn that the profile belongs to a different board, keep it for reference only, and start a new profile.
- Also record the board model, receiver profile, and software version in the file.
- Never claim the model guarantees holdover accuracy.

## 2. Networked SDR

Extend the SDR roadmap so a receiver on the station can be tuned from another machine on the LAN.

- Candidates: `rtl_tcp`, SoapyRemote, or OpenWebRX for a browser waterfall.
- LAN only, admin token required to start or change a shared receiver.
- Each option ships as its own feature branch so people can test them separately before one is merged.
- Timestamps and frequency reference state come from the station, as in the SDR roadmap.

## 3. Assisted network deploys

Let a coding agent on the operator's machine deploy to the station and check results, without unattended changes.

- SSH key login only; station address kept in a local, ignored config, never in the repo.
- The agent runs the existing deploy script and post-deploy checks, and must ask the operator before each deploy.
- The first deploy on a fresh station stays manual, because it shows the admin token.

## 4. PPS evidence capture script

From the original incident plan. *The script is built (#PR); the button is not.*

- `scripts/capture-pps-evidence.sh`: read-only; saves `/dev/pps*` listing, sysfs PPS state, a short `ppstest`, `chronyc` sources/sourcestats/tracking, PPS kernel messages, relevant config lines, service states, and a few seconds of gpsd output to one timestamped archive.
- Respects privacy mode (strips coordinates).
- Run it before rebooting during any future timing incident.
- Later: a read-only button on the PPS diagnostics page that produces the same archive.

## 5. Smaller items noted along the way

- Filter the station's own address out of chrony sources picked up from DHCP.
- Calibrate the NMEA refclock offset from measured data.
- Split the web bundle (currently ~750 kB) so the Pi serves less on first load.
- Downstream NTP: other routers or devices (e.g. a Turris Omnia) syncing from the station.
