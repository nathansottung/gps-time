"""Build reproducible-ish development and Pi deployment archives.

The Pi archive ships the built web UI (web/dist) so /app/ works on a station
without Node. Build it first: cd web && corepack pnpm install --frozen-lockfile
&& corepack pnpm run build. --without-web skips it (then /app/ returns 503).

No network access is required. The Pi installer may still fetch third-party
runtime dependencies/ephemerides unless a future offline dependency pack is
provided.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import io
import os
import subprocess
import tarfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DIST = ROOT / "dist"
EXCLUDE_DIRS = {".git", ".dev", "dist", "generated", "node_modules", "__pycache__", ".pytest_cache", ".mypy_cache"}
WEB_DIST = ROOT / "web" / "dist"
EXCLUDE_SUFFIXES = {".pyc", ".pyo", ".bsp", ".log", ".sha256"}
# Station state and secrets: never archived, whatever git says (review GPS-022).
EXCLUDE_NAMES = {"config.json", "config.json.prev", "admin-token.sha256", "timing-events.json", "station-key", "station-key.pub"}
# Everything install.sh (and the scripts it runs) reads from the bundle. tests/test_bundle_install.py
# runs install.sh from an extracted bundle, so a missing entry fails CI, not a deploy (v1.6.0-rc.1
# shipped without modules/ and install.sh stopped at `cp -r modules`).
PI_TOP = ["gps_time_pi", "schemas", "scripts", "system", "modules", "examples", "install.sh", "requirements.txt",
          "gps-time-pi.service", "README.md", "LICENSE", "THIRD_PARTY_NOTICES.md", "third_party", "SECURITY.md"]


EXECUTABLE_SUFFIXES = {".sh"}
# Generated per build (an installed station has no .git); a stray copy on disk is never archived.
VERSION_ARC = Path("gps_time_pi") / "VERSION"


def source_version() -> str | None:
    """``git describe`` of this checkout, via gps_time_pi/version.py; None without a reachable tag."""
    spec = importlib.util.spec_from_file_location("_gtp_version", ROOT / "gps_time_pi" / "version.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.describe(ROOT)


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


def git_tracked(root: Path = ROOT) -> set[str] | None:
    """Paths git tracks under root (POSIX, relative), or None outside a git checkout (e.g. an
    unpacked archive). Only tracked files are archived, so an untracked .env, config.json or
    token file in a checkout never ends up in a bundle (review GPS-022)."""
    try:
        out = subprocess.run(["git", "-C", str(root), "ls-files", "-z"], capture_output=True, check=True).stdout
    except (OSError, subprocess.CalledProcessError):
        return None
    return {p for p in out.decode("utf-8").split("\x00") if p}


_TRACKED: set[str] | None | bool = False   # computed once per run


def _tracked() -> set[str] | None:
    global _TRACKED
    if _TRACKED is False:
        _TRACKED = git_tracked()
    return _TRACKED


def wanted(path: Path, tracked: set[str] | None | bool = False) -> bool:
    """tracked: the git-tracked set to require (default: this checkout's; None: no git, filters only)."""
    rel = path.relative_to(ROOT)
    if rel == VERSION_ARC:
        return False
    if any(part in EXCLUDE_DIRS for part in rel.parts):
        return False
    if path.suffix in EXCLUDE_SUFFIXES or path.name in EXCLUDE_NAMES or path.name.startswith(".env"):
        return False
    if not path.is_file():
        return False
    tracked = _tracked() if tracked is False else tracked
    return tracked is None or rel.as_posix() in tracked


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def web_dist_problem(web_dist: Path, version: str | None) -> str | None:
    """Why this built UI must not be shipped, or None if it can be.

    The Vite build writes version.txt (the git describe it was built from); a
    UI built from another commit than the bundle is refused instead of shipped."""
    if not (web_dist / "index.html").is_file():
        return f"{web_dist} has no index.html: the web UI is not built"
    stamp = web_dist / "version.txt"
    built = stamp.read_text(encoding="utf-8").strip() if stamp.is_file() else None
    if version and built != version:
        return f"{web_dist} was built from {built or 'an unknown version'}, but this checkout is {version}: rebuild the web UI"
    return None


def build_repo_zip(out: Path, version: str | None = None):
    version = version or source_version()
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for p in sorted(ROOT.rglob("*")):
            if wanted(p):
                info = zipfile.ZipInfo.from_file(p, Path("gps-time") / p.relative_to(ROOT))
                info.external_attr = (0o100000 | archive_mode(p)) << 16
                info.compress_type = zipfile.ZIP_DEFLATED
                z.writestr(info, p.read_bytes())
        if version:
            info = zipfile.ZipInfo(f"gps-time/{VERSION_ARC.as_posix()}", (1980, 1, 1, 0, 0, 0))
            info.external_attr = (0o100000 | 0o644) << 16
            info.compress_type = zipfile.ZIP_DEFLATED
            z.writestr(info, version + "\n")


def build_pi_tar(out: Path, version: str | None = None, web_dist: Path | None = None):
    """web_dist: a built web UI to ship as gps-time/web/dist (served at /app/); None ships none."""
    version = version or source_version()
    with tarfile.open(out, "w:gz") as t:
        if version:
            data = (version + "\n").encode("utf-8")
            tinfo = _tar_member(tarfile.TarInfo(f"gps-time/{VERSION_ARC.as_posix()}"))
            tinfo.size = len(data)
            t.addfile(tinfo, io.BytesIO(data))
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
        if web_dist is not None:
            for child in sorted(Path(web_dist).rglob("*")):
                if child.is_file():
                    t.add(child, arcname=Path("gps-time/web/dist") / child.relative_to(web_dist), filter=_tar_member)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--without-web", action="store_true",
                    help="build the Pi archive without web/dist (/app/ will return 503 on the station)")
    args = ap.parse_args(argv)
    version = source_version()
    web_dist = None
    if not args.without_web:
        problem = web_dist_problem(WEB_DIST, version)
        if problem:
            raise SystemExit(f"error: {problem}.\n"
                             "  cd web && corepack pnpm install --frozen-lockfile && corepack pnpm run build\n"
                             "or pass --without-web to build a bundle with no /app/.")
        web_dist = WEB_DIST
    DIST.mkdir(exist_ok=True)
    repo = DIST / "gps-time-development.zip"
    pi = DIST / "gps-time-pi-deploy.tar.gz"
    build_repo_zip(repo)
    build_pi_tar(pi, version, web_dist)
    print("version:", version or "unknown (no reachable v* tag)")
    print("web UI:", "web/dist included (/app/)" if web_dist else "NOT included (--without-web)")
    manifest = DIST / "SHA256SUMS.txt"
    manifest.write_text(f"{sha256(repo)}  {repo.name}\n{sha256(pi)}  {pi.name}\n", encoding="utf-8")
    print(repo)
    print(pi)
    print(manifest)


if __name__ == "__main__":
    main()
