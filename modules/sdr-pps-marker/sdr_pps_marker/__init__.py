"""PPS time markers in SDR sample streams: research step 1 (synthetic).

See ../README.md and docs/specs/SPEC-SDR-PPS-MARKER.md.
"""

from .detector import Marker, detect
from .timemodel import TIME_SOURCE, TimeModel, UtcTime

__all__ = ["Marker", "detect", "TimeModel", "UtcTime", "TIME_SOURCE"]
