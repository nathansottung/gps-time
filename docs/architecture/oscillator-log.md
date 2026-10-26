# Oscillator log: temperature with chrony's frequency

Status: implemented (`gps_time_pi/oscillator.py`, `/api/oscillator`, Timing → Oscillator in `/app/`). It is the data collection for the trained oscillator profile (`roadmap/ROADMAP-OSCILLATOR-AND-MISC.md` §1). The profile's fit is built (`gps_time_pi/oscprofile.py`, #133, "The profile fit" below); its holdover projection, export/import and board-bound file are not. Not yet run on a Pi.

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

## The profile fit

`gps_time_pi/oscprofile.py`, in `/api/oscillator` → `profile`, labelled `modeled`. Timing → Oscillator → "Oscillator Profile (fit)", with its curve on the scatter.

- **Data:** every bin with PPS selected throughout, from the whole file (read at start, then each bin as it closes), up to 90 days. That is more than the 7 days the charts show. Bins without PPS throughout never enter the fit.
- **Model**, in ppm: f(T, t) = a + b·(T − T0) [+ c·(T − T0)²] [+ d·days since the first bin]. T0 is the mean temperature of the bins used.
  - The quadratic term is a candidate only with at least 8 °C of range, and aging only with at least 3 days of data.
  - The candidate with the lowest BIC is kept, so a term must improve the fit by more than it costs.
  - All candidates' BIC are reported.
- **Robustness:** one pass of outlier removal (more than 5 robust SDs from the first fit). The count is reported.
- **Needs:** 72 PPS bins (12 hours) and 3 °C of range. Until then `status` is `insufficient`, with the reason.
- **Reported:** each term with its standard error; the residual RMS; R²; bins used and outliers; the temperature range and time span covered. `oscprofile.predict()` evaluates the model and says when a request is outside what it covers.
- **Display:** coefficients as Δf/f ×10⁻ⁿ (per °C, per °C², per day), with ppm in brackets.
- **What it isn't:** a measurement of the crystal (the sensor is the processor's), valid outside the range and span it covers, or a holdover guarantee.

## Holdover projection (GPS-008)

`oscprofile.holdover()`, from the last one-minute sample. Three projections of the time until the clock is off by ±1 µs, 10 µs, 100 µs, 1 ms, 10 ms, 100 ms and 1 s if GPS and PPS went away now. All three are labelled `modeled`:

- **Free-running (untrained):** |chrony Frequency|, how fast the clock would run with no correction. This is what the legacy page showed as "holdover".
- **Trained (skew only):** chrony keeps applying its learned frequency, and the error grows at Skew, chrony's own bound on that frequency. No temperature, no aging. The review's fix for GPS-008.
- **Profile:** Skew, plus the profile's residual RMS (wander the fit doesn't explain), plus the largest frequency change the profile gives for any temperature in the last 24 h's range of bin means (±5 °C from now until a day is logged), plus the aging term as a frequency ramp. The rates are added as magnitudes, as if the worst temperature were reached at once: pessimistic on purpose. The error is rate·τ + aging·τ²/2, solved for each threshold. A range beyond what the profile covers is flagged as extrapolated.

None of them has been checked against a real outage. That needs the offset measured when PPS comes back (OBS §6, the Holdover Performance card, still planned). The note on the payload says so.

## Export, import and board binding

- **Export:** `GET /api/oscillator/profile` returns one JSON file (`gps-time-oscillator-profile/1`). It holds the fitted profile; the fit bins as `[epoch s, °C, ppm]` rows (≤ 90 days, about 360 kB); the board's serial hash and model; the receiver's driver and firmware; the software version; and the export time. No position and no raw serial.
- **Import:** `POST /api/oscillator/profile` with that file, admin token required. The route accepts up to 2 MB (other POSTs: 256 kB). Each row is checked: time from 2000 to now + 1 day, −50 to 150 °C, ±1000 ppm, at most 90 days of bins.
- **Board binding:** the file's serial hash is compared with this board's.
  - **match:** the bins are merged into the fit (a bin the log already has wins). The file is written next to the log as `oscillator-profile.json`, merged with any earlier import, in one atomic write.
  - **mismatch:** the file is written as `oscillator-profile-reference.json`. It is shown with a warning, and its profile is refitted for display. It is never fitted with this board's data or used for a projection. This board's own profile carries on from its own log.
  - **unverifiable:** either hash is missing or malformed. The file is treated as reference only, the same as a mismatch.
- **At every start** both files are read and the binding is checked again. An imported file on an SD card moved to another Pi becomes reference only.
- **Writes:** only when an operator imports, never periodically.
- **Demo mode:** the import is checked and answered, but nothing is saved.
