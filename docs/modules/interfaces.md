# Module interfaces

Code: [`gps_time_pi/modkit/interfaces.py`](../../gps_time_pi/modkit/interfaces.py). Interface version **1.0.0**.

## Versioning

- The interface, the manifest format and the schemas follow semantic versioning, separately from the app.
- A module states the version it needs as `interface = "M.m"`. It runs on any station interface with the same `M` and a minor version of at least `m`.
- Breaking changes only in a new major version, announced one release ahead with a migration note.

## Source

```python
class MySource(Source):
    def start(self, ctx): ...   # runs in its own thread; return when done or when stop() is called
    def stop(self): ...         # return promptly
```

Emits `Observation(time_ns, source, values, timing)`:
- `time_ns`: UTC as integer nanoseconds (a float can't hold nanoseconds at 1.8 × 10⁹ s).
- `values`: name → labeled value.
- `timing`: `ctx.timing_quality()` at the time of the observation.

## Reference

```python
class MyReference(Reference):
    def list(self, site): ...             # [Transmitter(id, frequency_hz, bandwidth_hz, position, position_source)]
    def predict(self, site, tx, t_ns): ...  # {"delay_s": labeled, "uncertainty_s": labeled}
```

`site` is the privacy-filtered position (rounded in rounded mode, `None` in hidden mode). Self-reported positions (ADS-B, AIS) are labeled `external`.

## Analysis

```python
class MyAnalysis(Analysis):
    def handle(self, observation): ...   # one observation (a dict) → Result or None
    def run(self, window): ...           # a list of observations → [Result]
```

`Result(time_ns, analysis, values, method, inputs, uncertainty)`.

## ctx

| Member | What |
|---|---|
| `ctx.now_ns()` | The station's UTC clock, integer nanoseconds |
| `ctx.timing_quality()` | `{"state", "offset_bound_s", ...}`; `{"state": "UNKNOWN", "offset_bound_s": None}` when the host gives none |
| `ctx.site()` | Position under the privacy mode, or `None` |
| `ctx.config` | The module's settings (`"demo": true` in demo mode) |
| `ctx.emit(item)` | Hand an `Observation` or `Result` to the host; invalid items are dropped and counted |
| `ctx.log` | Logger `gps_time_pi.module.<name>` |
| `ctx.storage` | `None`, or a size-capped store (`write(name, bytes)`, atomic; `read(name)`) when the manifest asks for `ram` or `disk:<N>MiB` and the host provides it |
