# Oscillator log: temperature with chrony's frequency

Status: implemented (`gps_time_pi/oscillator.py`, `/api/oscillator`, Timing → Oscillator in `/app/`). It is the data collection for the trained oscillator profile (`roadmap/ROADMAP-OSCILLATOR-AND-MISC.md` §1); the profile itself is not built yet. Not yet run on a Pi.

## What is recorded

Once a minute, from the timing chain's last `chronyc -n tracking`:

| Value | Source | Label |
|---|---|---|
| frequency | chrony's `Frequency`: how fast the uncorrected system clock runs, ppm, + = fast | observed (chrony's estimate) |
| skew, residual frequency | chrony's `Skew`, `Residual freq` | observed |
| temperature | `/sys/class/thermal/thermal_zone0/temp` | observed |
| PPS selected | the timing chain's status | |

- The temperature is the processor's sensor, **not the crystal's**. They follow each other only roughly, and with a lag. The page says so.
- With chrony unreadable, nothing is recorded for that minute. A missing temperature is stored as empty, never as zero.
- Samples taken while chrony was not using PPS are kept and marked, and never used for the fit.

## Storage

- One-minute samples are folded into **10-minute bins** in RAM: count, PPS count, mean/min/max temperature, mean/min/max frequency, mean skew and residual.
- Finished bins are **appended to `oscillator-log.csv`** next to `config.json` **once an hour** and on a clean stop (SIGTERM), with fsync: about six short lines an hour, never a write per sample.
- **Size cap** 4 MB by default (`GTP_OSCILLATOR_LOG_MAX_BYTES`), roughly a year of bins. Past it, the oldest quarter is dropped in one atomic rewrite.
- The last 7 days are kept in RAM for the page; on start the service reads them back from the file.
- **Board binding.** The file's first line holds a hash of the board's serial number (`/sys/firmware/devicetree/base/serial-number`; the raw serial is never stored or shown) and the board model. A file whose hash belongs to another board, for example after moving the SD card, is set aside as `oscillator-log.csv.set-aside-<time>` instead of being mixed in.
- A failed write keeps the bins in memory for the next try and reports the problem.

## What the page shows

- Frequency against temperature, one point per bin (PPS-only or all).
- A **straight-line slope**, ppm per °C, `calculated` from bins with PPS selected throughout. It needs 36 such bins (6 hours) and at least 2 °C of temperature range; otherwise the page says which is missing. **It is not the oscillator profile and not a holdover prediction.**
- Temperature and frequency over time, and the state of the log (size against the cap, bins waiting to be written, the board hash).

## Not done here

The roadmap's profile is still to come: a fitted model (temperature and slow aging) with its fit quality and span, holdover projections labeled `modeled`, and export/import as one JSON file bound to the board.
