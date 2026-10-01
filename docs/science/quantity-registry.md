# Scientific quantity and unit registry

Use the best scientific name in code/docs where practical. Friendly language belongs in ELI5 copy, not as a replacement for the canonical quantity.

| Friendly concept | Canonical quantity | Symbol | Canonical / conventional display unit |
|---|---|---|---|
| Clock offset | time offset | Δt | s; display ms, µs, ns |
| Clock "drift" | fractional frequency offset | Δf/f | dimensionless; display ppm/ppb |
| Frequency stability | Allan deviation | σᵧ(τ) | dimensionless |
| Time stability | time deviation | TDEV | s |
| Time interval error | TIE / MTIE | — | s |
| Light-distance equivalent | propagation distance corresponding to Δt | d=cΔt | m, km |
| Network latency | round-trip time / one-way delay | RTT / d | s, ms, µs |
| Satellite signal quality | carrier-to-noise-density ratio | C/N₀ | dB-Hz |
| GNSS geometry | dilution of precision | TDOP/HDOP/VDOP/PDOP | dimensionless |
| GNSS ellipsoid altitude | ellipsoidal height | h | m |
| Mean-sea-level elevation | orthometric height | H | m |
| Geoid correction | geoid undulation | N | m |
| Sun height | solar elevation angle | α | degree |
| Sun direction | solar azimuth | A | degree |
| Sun-relative time | apparent solar time | — | h:min:s |
| Seasonal solar stage | solar phase | — | dimensionless / % |
| Light power density | irradiance | G / E depending convention | W/m² |
| Daily solar energy per area | irradiation / radiant exposure | H | J/m²; display kWh/m²/day |
| Magnetic field | magnetic flux density | B | T; display µT/nT |
| RF frequency | frequency | f | Hz, kHz, MHz, GHz |
| SDR sampling | sampling rate | Fs | S/s, kS/s, MS/s |
| RF received power | received power | P | W / dBm when calibrated; dBFS when not |
| RF frequency error | frequency offset | Δf | Hz + fractional ppm/ppb |
| Event timing quality | timestamp uncertainty | u(t) | s/ns/µs and d=cΔt |
| Pressure | pressure | p | Pa; display hPa |
| Temperature | thermodynamic/Celsius temperature | T | K / °C display |
| Relative humidity | relative humidity | RH | % |
| Distance/bearing | geodesic distance / azimuth | s / α | m, km / degree |

Non-SI conventional units such as dB-Hz, dBm, ppm, degree and kWh are allowed when they are the standard domain representation. APIs should retain unambiguous units in field names or metadata.
