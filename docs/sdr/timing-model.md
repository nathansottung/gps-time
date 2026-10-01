# SDR timing model

Two independent questions must be answered:

1. **Sampling-rate accuracy:** how far apart are successive samples?
2. **Sample-epoch accuracy:** which UTC instant corresponds to sample N?

Frequency calibration alone does not establish epoch.

## Timing tiers

| Tier | Capability |
|---|---|
| SDR-0 | generic USB receive; host receipt time only |
| SDR-1 | sample-rate/frequency calibrated |
| SDR-2 | sample epoch calibrated/related to PPS |
| SDR-3 | distributed observation capable with stated uncertainty |
| SDR-4 | native PPS/reference clock/hardware timestamping for precision research |

## Frequency-dependent delay

Receiver delay is not necessarily one constant. RF filters, tuner state, sample rate, bandwidth, DSP filtering and temperature can change group delay. Calibration may therefore be represented as `τ(f, bandwidth, Fs, gain, temperature, configuration)` with measured uncertainty.

Known digital FIR/filter delay should be calculated exactly when possible; analog/RF delay is measured or left unknown.

## GPS-L1 experiment

An RTL-class SDR can be used with software GNSS to characterize aspects of its sample clock, but the GNSS RF signal does not contain a literal electrical PPS edge. Retuning can change RF-chain delay and may break a previously inferred sample epoch. Treat GPS reception as an experiment/calibration input, not a universal one-number offset.
