"""Application version, read from the git tag.

Resolved once, in this order:

1. ``gps_time_pi/VERSION``: written into deploy bundles by
   ``tools/build_bundles.py``, because an installed station has no ``.git``.
2. ``git describe --tags --match "v[0-9]*" --dirty`` in a checkout:
   ``1.4.0-rc.1`` on the tag, ``1.4.0-rc.1-3-gabc1234`` three commits later,
   with ``-dirty`` for uncommitted changes.
3. ``unknown``: no tag reachable (e.g. a shallow clone), or git missing.

The leading ``v`` of the tag is dropped.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

PACKAGE_DIR = Path(__file__).resolve().parent
VERSION_FILE = PACKAGE_DIR / "VERSION"
UNKNOWN = "unknown"


def normalize(tag: str) -> str | None:
    tag = tag.strip()
    if tag.startswith("v") and tag[1:2].isdigit():
        tag = tag[1:]
    return tag if tag and tag[0].isdigit() and len(tag) <= 64 and "\n" not in tag else None


def from_file(path: Path = VERSION_FILE) -> str | None:
    try:
        return normalize(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError):
        return None


def describe(repo: Path = PACKAGE_DIR.parent) -> str | None:
    """``git describe`` of the checkout at ``repo``, or None outside a checkout."""
    if not (repo / ".git").exists():
        return None
    try:
        out = subprocess.run(
            ["git", "-C", str(repo), "describe", "--tags", "--match", "v[0-9]*", "--dirty"],
            capture_output=True, text=True, timeout=5, check=False)
    except (OSError, subprocess.SubprocessError):
        return None
    return normalize(out.stdout) if out.returncode == 0 else None


def app_version(path: Path = VERSION_FILE, repo: Path = PACKAGE_DIR.parent) -> str:
    return from_file(path) or describe(repo) or UNKNOWN
