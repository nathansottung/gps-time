# Compute and resource tiers

Every optional module should declare its expected CPU, RAM, persistent-write, network and timing requirements.

| Capability | Station node | Analysis node | Coordinator |
|---|---|---|---|
| GNSS/PPS + chrony/NTP | required | — | — |
| Astronomy/solar/geodesy | yes | optional | — |
| Weather/small sensors | yes | optional archive | optional aggregate |
| ADS-B 1090 / UAT 978 decoding | yes | optional history | optional feed/aggregate |
| One/few SDR spectrum tasks | yes, bounded | optional | — |
| Wideband continuous IQ archive | limited | preferred | — |
| MLAT/TDoA solving | small experiments | preferred | possible |
| Cross-correlation of many captures | no/limited | preferred | possible |
| Regional terrain/maps | optional pack | preferred large pack | — |
| Multi-station history | summary only | preferred | preferred |

A module must fail closed/unavailable rather than consume resources indefinitely.
