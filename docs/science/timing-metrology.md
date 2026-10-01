# Timing metrology and error budgets

## Light-distance representation

The speed of light in vacuum is exact by SI definition: `c = 299,792,458 m/s`.

The dashboard may display `d = c × |Δt|` as an educational equivalent distance. This does **not** mean a station can localize an event to that distance; sensor-chain, geometry and propagation errors also matter.

Examples:

- 1 s ≈ 299,792 km
- 1 ms ≈ 299.8 km
- 1 µs ≈ 299.8 m
- 100 ns ≈ 30.0 m
- 10 ns ≈ 3.0 m
- 1 ns ≈ 0.300 m

## Station timing chain

```text
GNSS signal
→ antenna phase center
→ coax / RF group delay
→ GNSS receiver solution
→ PPS output
→ HAT traces / wiring
→ GPIO/kernel PPS timestamp
→ chrony/system clock
→ network or local sensor/application timestamp
```

Record separately:

- fixed bias that can be calibrated/compensated
- random jitter/uncertainty
- model/datasheet assumptions
- environmental dependence
- calibration date/method

## Holdover

A simple projection from chrony's fractional frequency correction can estimate how long a free-running oscillator would take to accumulate a stated error. Label it as a projection. A stronger future model uses actual GPS-loss experiments and temperature history.

## Future metrics

Allan deviation, modified Allan deviation, TDEV, TIE and MTIE belong in the timing-lab module once collection semantics are correct.
