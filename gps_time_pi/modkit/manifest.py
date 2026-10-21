"""Read and check a module's manifest (module.toml).

The schema (schemas/manifest.v1.json) checks shapes; this adds what a schema
can't: the name matches the folder, every code type (source, reference,
analysis) has an entry point, and the interface version is one this station
can run.
"""

import tomllib
from dataclasses import dataclass
from pathlib import Path

from . import schema
from .interfaces import INTERFACE_VERSION, TYPE_BASES

CODE_TYPES = tuple(TYPE_BASES)


@dataclass(frozen=True)
class Manifest:
    name: str
    version: str
    types: tuple
    maturity: str
    interface: str
    entry: dict
    permissions: dict
    data: dict          # the whole parsed file
    path: Path          # the module's folder


def interface_compatible(required, provided=INTERFACE_VERSION):
    """A module needing "M.m" runs on an interface M.n.p with the same M and n >= m."""
    try:
        rmaj, rmin = (int(x) for x in required.split("."))
        pmaj, pmin = (int(x) for x in provided.split(".")[:2])
    except (AttributeError, ValueError):
        return False
    return rmaj == pmaj and rmin <= pmin


def read(module_dir):
    """(Manifest, []) when valid, else (None, errors)."""
    module_dir = Path(module_dir)
    f = module_dir / "module.toml"
    try:
        data = tomllib.loads(f.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None, [f"{module_dir.name}: no module.toml"]
    except (tomllib.TOMLDecodeError, UnicodeDecodeError) as e:
        return None, [f"{module_dir.name}: module.toml is not valid TOML ({e})"]
    errs = [f"{module_dir.name}: {e}" for e in schema.validate(data, schema.load("manifest.v1"))]
    if errs:
        return None, errs
    if data["name"] != module_dir.name:
        errs.append(f"{module_dir.name}: name {data['name']!r} does not match the folder")
    entry = data.get("entry", {})
    for t in data["types"]:
        if t in CODE_TYPES and t not in entry:
            errs.append(f"{module_dir.name}: type {t} needs an entry point ([entry] {t} = \"package.module:Class\")")
    for t in entry:
        if t not in data["types"]:
            errs.append(f"{module_dir.name}: entry {t} is not one of the module's types")
    if not interface_compatible(data["interface"]):
        errs.append(f"{module_dir.name}: needs interface {data['interface']}; this station provides {INTERFACE_VERSION}")
    if errs:
        return None, errs
    return Manifest(data["name"], data["version"], tuple(data["types"]), data["maturity"], data["interface"],
                    dict(entry), dict(data["permissions"]), data, module_dir), []
