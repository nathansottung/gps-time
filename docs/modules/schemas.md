# Module data schemas

Versioned JSON Schema files in [`schemas/`](../../schemas/). A breaking change needs a new version file (`*.v2.json`); old versions stay.

| File | What | Checked by |
|---|---|---|
| `observation.v1.json` | `Observation` from a source: `schema`, `time_ns`, `source`, `values`, `timing` | the loader, on every `ctx.emit` |
| `result.v1.json` | `Result` from an analysis: values, `method`, `inputs`, `uncertainty` | the loader, on every `ctx.emit` |
| `manifest.v1.json` | `module.toml`, parsed | `gps_time_pi.modkit.manifest`, plus the rules a schema can't express |
| `sigmf-gpstime.v1.json` | The global object of an observation file (SigMF + `gpstime:`) | `gps_time_pi.obsformat`, plus checksum, captures, times and the privacy rule ([observation-format.md](observation-format.md)) |

Every value inside `values` and `uncertainty` is a **labeled value**: `{"value", "unit", "provenance"[, "note"]}`. The provenance is one of observed, calculated, modeled, predicted, inferred or external.

The station checks these files with a small standard-library checker (`gps_time_pi/modkit/schema.py`). It supports the subset the files use: type, required, properties, additionalProperties, enum, const, items, minimum, minLength, pattern, and `$ref` to `#/$defs/...`.

Events keep the station's existing event model. Sample data goes in observation files: [observation-format.md](observation-format.md).
