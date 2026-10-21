# Open-source and dependency policy

## Project-authored work

All project-authored application code, schemas, APIs, calibration formats, dashboard widgets, distributed-observation protocols, reference solvers and documentation are intended to remain open source under the repository license unless an explicit documented licensing change is made.

No core scientific capability should require a proprietary cloud service or closed protocol.

## Third-party material

Do not relicense or imply ownership of:

- commercial receiver/SDR firmware
- vendor SDKs/drivers
- external web services
- map/terrain/astronomy/orbital datasets
- third-party decoding/MLAT software

Adapters may support them. Redistribution requires the original license to permit it.

Every bundled dataset/dependency should have source, version/revision, license, attribution, transformation/provenance and checksum where practical.

The current list is [`THIRD_PARTY_NOTICES.md`](../../THIRD_PARTY_NOTICES.md) at the repository root (with the license texts that must travel with shipped files in `third_party/licenses/`). It ships in the Pi bundle.

## Offline packs

Data packs must have manifests and support installation from local files/USB. Time-sensitive data must expose age/validity rather than silently appearing current.
