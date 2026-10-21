"""Module interfaces (docs/modules/interfaces.md, SPEC-EXTENSIBILITY.md).

A module implements one or more of Source, Reference and Analysis. Values a
module emits are labeled with gps_time_pi.labels.q (value, unit, provenance).

INTERFACE_VERSION follows semantic versioning, separately from the app: a
module names the version it needs in its manifest (`interface = "1.0"`), and
the loader refuses a module whose major version differs or whose minor version
is newer than this one.
"""

from dataclasses import asdict, dataclass, field

INTERFACE_VERSION = "1.0.0"
OBSERVATION_SCHEMA = "observation/1"
RESULT_SCHEMA = "result/1"


@dataclass
class Observation:
    """A timestamped observation from a source (schemas/observation.v1.json)."""
    time_ns: int                       # UTC, integer nanoseconds
    source: str                        # module name
    values: dict                       # name -> labeled value {value, unit, provenance[, note]}
    timing: dict = field(default_factory=dict)   # station timing-quality snapshot (ctx.timing_quality())
    schema: str = OBSERVATION_SCHEMA

    def to_dict(self):
        return asdict(self)


@dataclass
class Result:
    """An analysis result (schemas/result.v1.json)."""
    time_ns: int
    analysis: str                      # module name
    values: dict                       # name -> labeled value
    method: str
    inputs: list = field(default_factory=list)   # observation or file IDs used
    uncertainty: dict = field(default_factory=dict)
    schema: str = RESULT_SCHEMA

    def to_dict(self):
        return asdict(self)


@dataclass
class Transmitter:
    """A signal with a known or self-reported position (Reference.list)."""
    id: str
    frequency_hz: float
    bandwidth_hz: float
    position: dict                     # {lat, lon, alt_m} at the precision the source gives
    position_source: str               # e.g. "FCC licence 2026-10-01", "self-reported (ADS-B)"


class Source:
    """Reads a device (or fixtures in demo mode) and emits Observations through ctx.emit()."""

    def start(self, ctx):
        raise NotImplementedError

    def stop(self):
        """Ask the source to stop; must return promptly."""


class Reference:
    """Signals with known or self-reported transmitter positions."""

    def list(self, site):
        """Transmitters near the privacy-filtered site."""
        raise NotImplementedError

    def predict(self, site, tx, t_ns):
        """Expected delay from tx to site at time t: {"delay_s": labeled value, "uncertainty_s": ...}."""
        raise NotImplementedError


class Analysis:
    """Turns observations into Results (handle one, or run over a window)."""

    def handle(self, observation):
        raise NotImplementedError

    def run(self, window):
        raise NotImplementedError


TYPE_BASES = {"source": Source, "reference": Reference, "analysis": Analysis}
