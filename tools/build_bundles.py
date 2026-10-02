"""Build reproducible-ish development and Pi deployment archives.

No network access is required. The Pi installer may still fetch third-party
runtime dependencies/ephemerides unless a future offline dependency pack is
provided.
"""
from __future__ import annotations

import hashlib
import os
import tarfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DIST = ROOT / "dist"
EXCLUDE_DIRS = {".git", ".dev", "dist", "__pycache__", ".pytest_cache", ".mypy_cache"}
EXCLUDE_SUFFIXES = {".pyc", ".pyo"}
PI_TOP = ["gps_time_pi", "scripts", "system", "examples", "config", "install.sh", "requirements.txt", "gps-time-pi.service", "README.md", "LICENSE", "SECURITY.md"]


EXECUTABLE_SUFFIXES = {".sh"}


def archive_mode(path: Path) -> int:
    """Explicit POSIX mode for an archived file. Never inherit the builder's
    filesystem mode: Windows has no execute bit, which previously shipped
    logsync.sh as 0644 (CHG-002)."""
    return 0o755 if path.suffix in EXECUTABLE_SUFFIXES else 0o644


def _tar_member(tinfo: tarfile.TarInfo) -> tarfile.TarInfo:
    tinfo.mode = archive_mode(Path(tinfo.name))
    tinfo.uid = tinfo.gid = 0
    tinfo.uname = tinfo.gname = "root"
    return tinfo


def wanted(path: Path) -> bool:
    rel = path.relative_to(ROOT)
    if any(part in EXCLUDE_DIRS for part in rel.parts):
        return False
    if path.suffix in EXCLUDE_SUFFIXES:
        return False
    return path.is_file()


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def build_repo_zip(out: Path):
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for p in sorted(ROOT.rglob("*")):
            if wanted(p):
                info = zipfile.ZipInfo.from_file(p, Path("gps-time") / p.relative_to(ROOT))
                info.external_attr = (0o100000 | archive_mode(p)) << 16
                info.compress_type = zipfile.ZIP_DEFLATED
                z.writestr(info, p.read_bytes())


def build_pi_tar(out: Path):
    with tarfile.open(out, "w:gz") as t:
        for name in PI_TOP:
            p = ROOT / name
            if not p.exists():
                continue
            if p.is_file():
                t.add(p, arcname=Path("gps-time") / name, filter=_tar_member)
            else:
                for child in sorted(p.rglob("*")):
                    if wanted(child):
                        t.add(child, arcname=Path("gps-time") / child.relative_to(ROOT), filter=_tar_member)


def main():
    DIST.mkdir(exist_ok=True)
    repo = DIST / "gps-time-development.zip"
    pi = DIST / "gps-time-pi-deploy.tar.gz"
    build_repo_zip(repo)
    build_pi_tar(pi)
    manifest = DIST / "SHA256SUMS.txt"
    manifest.write_text(f"{sha256(repo)}  {repo.name}\n{sha256(pi)}  {pi.name}\n", encoding="utf-8")
    print(repo)
    print(pi)
    print(manifest)


if __name__ == "__main__":
    main()
