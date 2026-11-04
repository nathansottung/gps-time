# Stability analysis (ADEV, MDEV, TDEV)

Status: implemented (`gps_time_pi/stability.py`, `/api/stability`, Timing → Stability in `/app/`). Requirement: `specs/SPEC-TIMING-METROLOGY.md` §1. Not yet run on a Pi.

## What is measured

The input is a phase (time-error) series: the fractional second of each kernel PPS timestamp. That is where the Linux system clock, as chrony disciplines it, read when the PPS interrupt was stamped. chrony's PPS refclock consumes the same samples.

Timestamps are integer nanoseconds from the kernel's `<sec>.<nsec>` text on (`pps.read_assert`; since #153). The phase is found in integer arithmetic (`pps.phase_ns`) and only then turned into seconds, so it keeps every nanosecond. Before #153 the whole timestamp was a float of seconds, which near today's epoch steps in about 238 ns: phases smaller than that were lost (a ±37 ns phase read as 0). `Recorder.add` refuses a float.

So the statistics describe **the system clock against the PPS edges as Linux saw them**. They include interrupt latency and chrony's own control loop. They do not describe the receiver's electrical PPS, and they do not describe the oscillator alone. Every payload and the page say this.

All values are labeled `calculated`. The identified noise type is labeled `inferred`.

**Difference from the spec's wording.** The spec says "from chrony PPS offset history". chrony reports a PPS offset only once per refclock poll (16 s by default), which can't give a 1 s averaging time. The kernel timestamps are the per-second samples behind chrony's figure, so they are used instead.

## Statistics

Definitions follow NIST SP 1065 (Riley, *Handbook of Frequency Stability Analysis*).

| Statistic | Meaning | Unit |
|---|---|---|
| ADEV | overlapping Allan deviation σy(τ) | dimensionless (shown as ×10⁻ⁿ) |
| MDEV | modified Allan deviation | dimensionless |
| TDEV | time deviation, τ · MDEV / √3 | seconds |

Rules:

- ADEV at an averaging time τ needs 3τ of data, MDEV and TDEV need 4τ. A value is never given on less.
- A second with no PPS sample is a gap. A term that touches a gap is left out; nothing is interpolated.
- With no PPS events at all, the answer is `available: false` with the reason. It is never zero.
- The payload gives the share of the 1 s series during which chrony had the PPS refclock selected. Samples taken under another source describe the clock under that source, measured against PPS.

## Confidence bars

- For ADEV only. No interval is calculated for MDEV or TDEV.
- The interval is 68.3 %, from the chi-squared distribution with the equivalent degrees of freedom for the overlapping Allan variance (SP 1065 §5.4.1).
- The degrees of freedom depend on the power-law noise type (white PM, flicker PM, white FM, flicker FM, random-walk FM). It is identified at each τ with the lag-1 autocorrelation method (SP 1065 §5.5.6), which needs 30 points after decimation.
- With fewer than 30 points, the type found at a shorter τ is kept and the point is marked `noise_assumed`. The interval at such a point may be too narrow if the noise changes character at long τ.

## Storage

RAM only, lost on a service restart. Nothing is written to disk.

| Series | Content | Size | Averaging times |
|---|---|---|---|
| seconds | one phase sample per second | 4 h (14 400) | 1 s to 2000 s |
| minutes | per minute: the last sample, and the mean of the minute | 14 d (20 160) | 1 h to 2 d |

The minute summaries are exact inputs, not approximations:

- ADEV at τ ≥ 60 s needs only phase samples τ apart, so the minute's last sample (second 59) is enough.
- MDEV averages phase over each τ window. The mean of a whole number of minutes is that average, so the minute means give the 1 s definition on a one-minute grid. A minute with fewer than 54 samples has no mean.

A PPS timestamp that goes backwards (the clock was stepped back) restarts the history; the payload counts these.

## Poll timing

The timing-chain service reads the kernel's last PPS timestamp once per second. It used to sleep one second after each read, so its period was one second plus the read's own duration, and the read drifted across the pulse and skipped one from time to time. It now polls on a fixed grid, 0.25 s after each whole second (`timing_chain.next_tick_delay`). With the clock on PPS each pulse is read once. This changes only when the station software looks; it changes nothing in chrony, gpsd or the PPS setup.

## Cost

The statistics are computed when `/api/stability` is requested, at most once a minute (the answer is cached for 60 s). A full recalculation takes under a second on a desktop; it has not been timed on a Pi.

## Validation

`tests/test_stability.py` checks the estimators against the published reference values in SP 1065 §12.4:

- the 9-point NBS Monograph 140 data set (ADEV, MDEV, TDEV at averaging factors 1 and 2);
- the 1000-point test suite (ADEV, MDEV, TDEV at averaging factors 1, 10, 100), its noise type (white FM) and its degrees of freedom at factor 10 (146.177).

All agree to the seven digits published. The chi-squared quantiles are checked against standard table values.
