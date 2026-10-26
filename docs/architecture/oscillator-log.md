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

## Not done here

The rest of the roadmap's profile: the holdover projection labelled `modeled` beside the simple one (GPS-008), export/import as one JSON file, board binding on import, and the metadata in that file.
