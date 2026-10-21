#!/usr/bin/env python3
"""Create a new module with the full layout, a working fake and a passing test.

    python tools/new_module.py my-sensor --type source
    python tools/new_module.py tower-list --type reference
    python tools/new_module.py my-analysis --type analysis
    python tools/new_module.py my-card --type ui

Creates modules/<name>/ (or --dest/<name>/): module.toml, README.md, the
Python package (except for ui), fixtures/, tests/ and a web/ card stub. The
generated test passes as created; replace the fake with the real thing.
Guide: docs/modules/README.md.
"""

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from gps_time_pi.modkit.interfaces import INTERFACE_VERSION  # noqa: E402

TYPES = ("source", "reference", "analysis", "ui")
NAME_RE = re.compile(r"^[a-z][a-z0-9-]*[a-z0-9]$")
CLASS = {"source": "FakeSource", "reference": "FakeReference", "analysis": "FakeAnalysis"}

MANIFEST = '''# Module manifest. Guide: docs/modules/README.md; schema: schemas/manifest.v1.json.
name = "{name}"
version = "0.1.0"
types = ["{type}"]
maturity = "experimental"
interface = "{interface}"
summary = "TODO: one line on what {name} does"
{entry}
[hardware]
required = "none"   # TODO: e.g. "BME280-class sensor on I2C"

[timing]
needed = "s"        # TODO: "ms", "µs", "100 ns" ...
if_worse = "TODO: what the module does when the station's timing is worse than it needs"

[permissions]
network = false
devices = []        # TODO: e.g. ["/dev/i2c-1"]
storage = "none"    # none | ram | disk:<N>MiB

[config]
# TODO: settings, e.g. interval_s = {{ type = "float", unit = "s", default = 10.0 }}

[emits]
streams = ["example"]
events = []

[licence]
code = "MIT"
bundled_data = "none"
'''

README = '''# {name}

TODO: what it measures or does, in two sentences.

- **Type:** {type}. Maturity: experimental.
- **Hardware:** none yet (the fake runs from `fixtures/`).
- **Setup:** TODO.
- **Limits:** TODO. Say what it can't tell, and when it reports UNKNOWN.
- **Provenance:** every value it emits is labeled (observed, calculated, modeled, predicted, inferred, external).

## Tests

```bash
python -m unittest tests.test_modules -v
```

Maintainer: TODO. Licence: MIT.
'''

INIT = '''"""{name}: TODO one line. Guide: docs/modules/README.md."""
'''

SOURCE = '''"""{name}: the Source. Replace the fake with the device reader."""

import json
from pathlib import Path

from gps_time_pi.labels import q
from gps_time_pi.modkit import Observation, Source

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "sample.json"


class FakeSource(Source):
    def __init__(self):
        self._stop = False

    def stop(self):
        self._stop = True

    def start(self, ctx):
        # TODO: read the device. Until then, demo mode replays the fixture and
        # real mode emits nothing (never invent data).
        if not ctx.config.get("demo"):
            ctx.log.info("no device reader yet")
            return
        for row in json.loads(FIXTURE.read_text(encoding="utf-8"))["rows"]:
            if self._stop:
                return
            ctx.emit(Observation(time_ns=ctx.now_ns(), source="{name}",
                                 values={{"example": q(row["value"], row["unit"], "observed")}},
                                 timing=ctx.timing_quality()))
'''

REFERENCE = '''"""{name}: the Reference. Replace the fake list with the real catalogue."""

import json
import math
from pathlib import Path

from gps_time_pi.labels import q
from gps_time_pi.modkit import Reference, Transmitter

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "sample.json"
C = 299_792_458.0
EARTH_R = 6_371_000.0


class FakeReference(Reference):
    def list(self, site):
        if site is None:            # hidden privacy mode: nothing can be computed
            return []
        return [Transmitter(**t) for t in json.loads(FIXTURE.read_text(encoding="utf-8"))["transmitters"]]

    def predict(self, site, tx, t_ns):
        if site is None:
            return None
        p1, p2 = math.radians(site["lat"]), math.radians(tx.position["lat"])
        dl = math.radians(tx.position["lon"] - site["lon"])
        d = EARTH_R * math.acos(min(1.0, math.sin(p1) * math.sin(p2) + math.cos(p1) * math.cos(p2) * math.cos(dl)))
        return {{"delay_s": q(d / C, "s", "predicted", note="great-circle path; TODO: real propagation"),
                "uncertainty_s": q(None, "s", "predicted", note="TODO")}}
'''

ANALYSIS = '''"""{name}: the Analysis. Replace the fake with the real method."""

from gps_time_pi.labels import q
from gps_time_pi.modkit import Analysis, Result


class FakeAnalysis(Analysis):
    def handle(self, observation):
        v = observation["values"].get("example")
        if v is None or v["value"] is None:
            return None
        return Result(time_ns=observation["time_ns"], analysis="{name}", method="TODO: describe the method",
                      values={{"doubled": q(2 * v["value"], v["unit"], "calculated")}},
                      inputs=[str(observation["time_ns"])],
                      uncertainty={{"doubled": q(None, v["unit"], "calculated", note="TODO")}})

    def run(self, window):
        return [r for r in (self.handle(o) for o in window) if r is not None]
'''

FIXTURES = {
    "source": {"about": "Replayed by the fake source in demo mode.", "rows": [{"value": 1.5, "unit": "V"}, {"value": 1.6, "unit": "V"}]},
    "reference": {"about": "Example transmitter (US Naval Observatory position, an example only).",
                  "transmitters": [{"id": "example-1", "frequency_hz": 100.1e6, "bandwidth_hz": 200e3,
                                    "position": {"lat": 38.9217, "lon": -77.0669, "alt_m": 92.0},
                                    "position_source": "example"}]},
    "analysis": {"about": "Observations the fake analysis turns into results.",
                 "observations": [{"schema": "observation/1", "time_ns": 1792602000000000000, "source": "example",
                                   "values": {"example": {"value": 1.5, "unit": "V", "provenance": "observed"}},
                                   "timing": {"state": "UNKNOWN", "offset_bound_s": None}}]},
    "ui": {"about": "Data the card renders in the demo.", "rows": [{"label": "Example", "value": 1.5, "unit": "V"}]},
}

TEST = '''"""{name}: generated tests; they pass as created. Keep them passing as the module grows."""

import json
import unittest
from pathlib import Path

from gps_time_pi.modkit import ModuleContext, read_manifest
from gps_time_pi.modkit import schema

HERE = Path(__file__).resolve().parents[1]
FIX = json.loads((HERE / "fixtures" / "sample.json").read_text(encoding="utf-8"))


class TestManifest(unittest.TestCase):
    def test_manifest_is_valid(self):
        m, errs = read_manifest(HERE)
        self.assertEqual(errs, [])
        self.assertEqual(m.name, HERE.name)
{body}

if __name__ == "__main__":
    unittest.main()
'''

TEST_BODY = {
    "source": '''

class TestSource(unittest.TestCase):
    def run_source(self, demo):
        from {pkg}.source import FakeSource
        out = []
        FakeSource().start(ModuleContext("{name}", config={{"demo": demo}}, emit=out.append))
        return [o.to_dict() for o in out]

    def test_demo_emits_valid_labeled_observations(self):
        out = self.run_source(True)
        self.assertEqual(len(out), len(FIX["rows"]))
        for o in out:
            self.assertEqual(schema.validate(o, schema.load("observation.v1")), [])

    def test_real_mode_emits_nothing_until_there_is_a_reader(self):
        self.assertEqual(self.run_source(False), [])
''',
    "reference": '''

class TestReference(unittest.TestCase):
    SITE = {{"lat": 38.8895, "lon": -77.0353}}   # Washington Monument, an example point

    def test_list_and_predict(self):
        from {pkg}.reference import FakeReference
        ref = FakeReference()
        txs = ref.list(self.SITE)
        self.assertEqual(len(txs), len(FIX["transmitters"]))
        p = ref.predict(self.SITE, txs[0], 0)
        self.assertEqual(p["delay_s"]["provenance"], "predicted")
        self.assertGreater(p["delay_s"]["value"], 0)

    def test_hidden_site_gives_nothing(self):
        from {pkg}.reference import FakeReference
        self.assertEqual(FakeReference().list(None), [])
''',
    "analysis": '''

class TestAnalysis(unittest.TestCase):
    def test_results_are_valid(self):
        from {pkg}.analysis import FakeAnalysis
        results = FakeAnalysis().run(FIX["observations"])
        self.assertEqual(len(results), len(FIX["observations"]))
        for r in results:
            self.assertEqual(schema.validate(r.to_dict(), schema.load("result.v1")), [])
''',
    "ui": '''

class TestCard(unittest.TestCase):
    def test_card_stub_exists(self):
        self.assertTrue((HERE / "web" / "Card.tsx").is_file())
''',
}

CARD = '''// {name}: UI card stub. Follow web/guidelines/Guidelines.md and use the existing
// components (MetricRow, ProvenanceTag, MaturityBadge). Cards must render from the
// demo adapter with this module's fixtures. Not built into /app/ until the module
// UI hook exists (SPEC-EXTENSIBILITY, "UI cards").
export const MODULE = "{name}";
'''


def scaffold(name, kind, dest):
    if not NAME_RE.match(name):
        raise SystemExit(f"bad name {name!r}: lowercase letters, digits and hyphens, starting with a letter")
    if kind not in TYPES:
        raise SystemExit(f"bad type {kind!r}: one of {', '.join(TYPES)}")
    d = Path(dest) / name
    if d.exists():
        raise SystemExit(f"{d} already exists")
    pkg = name.replace("-", "_")
    major, minor = INTERFACE_VERSION.split(".")[:2]
    entry = f'\n[entry]\n{kind} = "{pkg}.{kind}:{CLASS[kind]}"\n' if kind in CLASS else ""
    files = {
        "module.toml": MANIFEST.format(name=name, type=kind, interface=f"{major}.{minor}", entry=entry),
        "README.md": README.format(name=name, type=kind),
        "fixtures/sample.json": json.dumps(FIXTURES[kind], indent=2) + "\n",
        f"tests/test_{pkg}.py": TEST.format(name=name, body=TEST_BODY[kind].format(name=name, pkg=pkg)),
        "web/Card.tsx": CARD.format(name=name),
    }
    if kind in CLASS:
        files[f"{pkg}/__init__.py"] = INIT.format(name=name)
        files[f"{pkg}/{kind}.py"] = {"source": SOURCE, "reference": REFERENCE, "analysis": ANALYSIS}[kind].format(name=name)
    for rel, text in files.items():
        p = d / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8", newline="\n")
    return d


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("name")
    ap.add_argument("--type", required=True, choices=TYPES)
    ap.add_argument("--dest", default=str(ROOT / "modules"))
    a = ap.parse_args(argv)
    d = scaffold(a.name, a.type, a.dest)
    print(f"created {d}")
    print("next: python -m gps_time_pi.modkit check, then python -m unittest tests.test_modules")
    return 0


if __name__ == "__main__":
    sys.exit(main())
