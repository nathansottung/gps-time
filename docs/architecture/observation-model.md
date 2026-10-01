# Observation model

The common observation record is the interoperability boundary for sensors and distributed science.

Minimum conceptual fields:

- observation type and schema version
- station identifier
- instrument identifier/model/serial where appropriate
- value(s) and canonical units
- observation epoch (UTC when available)
- timestamp method
- timestamp uncertainty
- station position and position uncertainty or privacy-preserving reference
- calibration profile identifier
- provenance: observed / calculated / modeled / inferred
- quality flags and freshness
- optional raw-data hash and content reference
- software/version metadata

Distributed solvers must consume uncertainty rather than treating all timestamps/positions as equally exact.
