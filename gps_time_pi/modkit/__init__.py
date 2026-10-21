"""Module kit: interfaces, manifest checks, ctx and the loader for optional modules.

Guide: docs/modules/README.md. Spec: docs/specs/SPEC-EXTENSIBILITY.md.
The web service doesn't use this package yet: a station behaves as before.
"""

from .context import CappedStorage, ModuleContext, StorageFull
from .interfaces import (INTERFACE_VERSION, Analysis, Observation, Reference, Result, Source,
                         Transmitter)
from .loader import ModuleHost, discover, enabled_from_config
from .manifest import interface_compatible, read as read_manifest

__all__ = ["INTERFACE_VERSION", "Source", "Reference", "Analysis", "Observation", "Result", "Transmitter",
           "ModuleContext", "CappedStorage", "StorageFull", "ModuleHost", "discover", "enabled_from_config",
           "interface_compatible", "read_manifest"]
