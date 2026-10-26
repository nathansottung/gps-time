"""GPS Time coordinator: SKELETON (docs/specs/SPEC-COORDINATOR.md, ADR-0008).

Accepts signed join requests and signed event batches from stations, keeps
devices pending until the owner approves them, and stores events in SQLite.
No processing services yet. Runs as a container (TrueNAS SCALE: coordinator/README.md).
Not part of the station bundle; nothing on a station talks to it yet.
"""

__version__ = "0.1.0"
