"""What a module gets from the station: ctx.

- now_ns(): the station's UTC clock, integer nanoseconds.
- timing_quality(): the station's timing state and offset bound, from the host
  (UNKNOWN when the host gives none).
- site(): the position under the station's privacy mode, from the host. A
  module never sees more than the mode allows (None in hidden mode).
- config: the module's own settings.
- emit(item): hands an Observation or Result to the host.
- log: a logger named after the module.
- storage: None unless the manifest asks for it; then a size-capped store.
"""

import logging
import os
import tempfile
import time
from pathlib import Path

UNKNOWN_TIMING = {"state": "UNKNOWN", "offset_bound_s": None}


class StorageFull(Exception):
    pass


class CappedStorage:
    """A module's own folder with a size cap. Writes are atomic (temporary file, then rename)."""

    def __init__(self, root, cap_bytes):
        self.root = Path(root)
        self.cap_bytes = int(cap_bytes)
        self.root.mkdir(parents=True, exist_ok=True)

    def used_bytes(self):
        return sum(p.stat().st_size for p in self.root.iterdir() if p.is_file())

    def _path(self, name):
        if not name or "/" in name or "\\" in name or name.startswith("."):
            raise ValueError(f"bad file name: {name!r}")
        return self.root / name

    def write(self, name, data: bytes):
        p = self._path(name)
        old = p.stat().st_size if p.exists() else 0
        if self.used_bytes() - old + len(data) > self.cap_bytes:
            raise StorageFull(f"{name}: would exceed {self.cap_bytes} bytes")
        fd, tmp = tempfile.mkstemp(dir=self.root, prefix=".tmp-")
        try:
            with os.fdopen(fd, "wb") as f:
                f.write(data)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp, p)
        except BaseException:
            if os.path.exists(tmp):
                os.unlink(tmp)
            raise

    def read(self, name):
        return self._path(name).read_bytes()


class ModuleContext:
    def __init__(self, name, *, config=None, emit=None, timing_quality=None, site=None,
                 storage=None, clock_ns=time.time_ns):
        self.name = name
        self.config = dict(config or {})
        self._emit = emit or (lambda item: None)
        self._timing = timing_quality or (lambda: dict(UNKNOWN_TIMING))
        self._site = site or (lambda: None)
        self._clock = clock_ns
        self.storage = storage
        self.log = logging.getLogger(f"gps_time_pi.module.{name}")

    def now_ns(self):
        return self._clock()

    def timing_quality(self):
        return self._timing()

    def site(self):
        return self._site()

    def emit(self, item):
        self._emit(item)
