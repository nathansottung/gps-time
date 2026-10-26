# Second pulse: the system clock on a wire

**Status:** tool, 2026-10-26 (#126). Bench use; nothing runs on a station unless you start it.

The station's own figures (offset, ADEV, holdover) compare the system clock with the PPS edges **as Linux timestamped them**. They can't show an error the kernel and chrony share. This puts the system clock back on a GPIO pin, so a scope or a time-interval counter can compare it with the receiver's PPS electrically, outside the Pi.

- **Pulse:** `python -m gps_time_pi.secpulse` (`gps_time_pi/secpulse.py`). A rising edge at each whole second of the system clock (CLOCK_REALTIME, as chrony disciplines it), 100 ms wide.
- **Comparison:** `python tools/pps_compare.py` reads the instrument's CSV and reports statistics, stability and what they say about the system clock.

It is the first step of the accuracy validation in `../SCOPE-REVIEW.md` §7 item 1. It does **not** measure PPS against UTC; that needs a second independent reference (a GPSDO, a second receiver, a second station; see "What it can't show").

## What is measured

| Symbol | Meaning |
|---|---|
| x | t(second-pulse edge) − t(PPS edge), from the instrument, after cable and probe delays |
| e | system clock minus PPS time (positive: the system clock is ahead) |
| L | latency from the system clock's second boundary to the GPIO edge: waking up, the write, the GPIO block. L ≥ 0 |

The edge goes out L after the system clock reads a whole second, so **x = L − e**.

- **Without a pulse log**, L is unknown, and only a bound follows: e ≥ −x. The tool reports this as "the system clock is not behind PPS by more than x" (calculated).
- **With `--log`**, secpulse records for each pulse the system clock just before the write and just after it returns. The edge is in that window if the clock reads correctly. Taking it at the window's middle gives an estimate of e with half the window as its uncertainty. That's a model, so the tool labels it `modeled`.

On a Raspberry Pi the write window is typically a few µs, and its tail depends on load. Run with `--rt` to reduce the tail, and leave the station's normal load on, because that's the condition being validated.

## Wiring

```
receiver PPS ──┬──────────────► Pi PPS input (pps-gpio, e.g. GPIO 18) — unchanged
               └──── tee ─────► instrument channel A (start)
Pi GPIO 23 (pin 16) ──────────► instrument channel B (stop)
Pi GND (pin 14) ──────────────► instrument ground
```

- **Pick a free line.** It must not be the PPS input: secpulse reads the `pps-gpio` overlay from `config.txt` and refuses that line. Check the receiver HAT's pinout too. GPIO 23 (header pin 16) isn't among the Uputronics GPS/RTC HAT's documented pins (PPS on GPIO 18, UART on 14/15, I²C on 2/3), but check your board.
- **Levels:** 3.3 V logic. Use high-impedance inputs (1 MΩ, or a 10× probe). A 50 Ω termination loads the Pi pin and slows the edge; if a counter only has 50 Ω inputs, buffer the signal first.
- **Keep the PPS tap high impedance** so it doesn't change the edge the Pi sees.
- **Trigger** both channels on the rising edge at about 1.5 V. If the receiver asserts on the falling edge (`assert_falling_edge` in the overlay), trigger channel A on falling.
- **Measure the cable and probe delays** of both channels, or use equal lengths, and pass the difference to the tool (`--delay-gpio-ns`, `--delay-pps-ns`). Coax is about 5 ns per metre.

## Run

On the station, over SSH (read-only for timing: chrony, gpsd and PPS are not touched):

```bash
python3 -m gps_time_pi.secpulse --line 23 --rt --log /dev/shm/secpulse.csv
```

- Use the venv Python on an installed station: `/opt/gps-time-pi/venv/bin/python`.
- It needs read/write access to `/dev/gpiochip0` (the `gpio` group on Raspberry Pi OS); `--rt` needs root or `CAP_SYS_NICE`.
- `--log` goes to `/dev/shm` (RAM), not the SD card, so nothing is written to the SD card at 1 Hz. Copy it off afterwards. Without `--log`, it prints one summary line per minute.
- To keep it running after you log out:

  ```bash
  sudo systemd-run --unit=gps-time-secpulse --working-directory=/opt/gps-time-pi /opt/gps-time-pi/venv/bin/python -m gps_time_pi.secpulse --line 23 --rt --log /dev/shm/secpulse.csv
  ```

  This runs as root. It opens one GPIO line and nothing else.

  Stop it with `sudo systemctl stop gps-time-secpulse`.

On the instrument:

- **Time-interval counter:** start on channel A (PPS), stop on channel B (pulse), one reading per second, export CSV. This is `gpio-minus-pps`, the tool's default.
- **Scope:** trigger on PPS, measure delay A→B (the scope's sign convention varies; check it with one manual reading), log the measurement per trigger, export CSV.

Run for at least an hour. A day shows temperature effects.

## Compare

```bash
python tools/pps_compare.py counter.csv --delay-gpio-ns 4.9 --delay-pps-ns 5.1 --pulse-log secpulse.csv
python tools/pps_compare.py scope.csv --column "Delay(C1-C2) (us)" --sign pps-minus-gpio
```

- **Input:** commas, semicolons, tabs or whitespace; header and comment lines; units from `--unit`, the header (`(us)`, `[ns]`) or each value (`850ns`, `1.2E-06 s`). With several numeric columns, it picks one whose header names an interval or delay, or asks for `--column`.
- **Pairing errors:** a value more than 0.5 s from zero (a missed or extra edge, or a counter overflow marker) is dropped and counted.
- **Outliers:** values more than 10 MADs (at least 1 µs) from the median are counted and left out of the statistics; `--keep-outliers` keeps them. The tool never names a cause for them.
- **Output:** n, mean, SD, median, percentiles, range, drift; ADEV and TDEV of x as a phase series at 1 s spacing; the bound, and with a pulse log the modeled offset. `--json` for the full report with provenance labels.

## What it can't show

- **PPS against UTC.** Both channels hang off the same receiver. The receiver's own PPS error, its quantization (sawtooth) and the antenna cable delay are invisible here. For that: a GPSDO or a second receiver with known delays, or a second station (`../hardware/`).
- **Kernel PPS timestamp latency, separately.** This measures the whole path from system clock to GPIO edge. A small or steady x shows that the path, including the kernel timestamps chrony steers by, agrees with the PPS edge. A large x has several possible contributors, and the tool doesn't pick one.
- **Holdover.** It needs a reference through the outage. Run it during an antenna disconnect only with the instrument's own reference, never the receiver's PPS.

## Files

- `gps_time_pi/secpulse.py`: the pulse loop and the GPIO character-device uAPI v2, standard library only.
- `tools/pps_compare.py`: parsing and analysis; reuses the ADEV/MDEV estimators in `gps_time_pi/stability.py`.
- `tests/test_secpulse.py`, `tests/fixtures/validation/`: synthetic fixtures (not measurements) in counter and scope export shapes, and a pulse log.
