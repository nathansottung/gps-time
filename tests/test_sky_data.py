"""Bundled sky data: built from OpenNGC and d3-celestial by tools/build_sky_data.py, each file
under its source's license (gps_time_pi/data/README.md, THIRD_PARTY_NOTICES.md). The builder is
tested on small synthetic fixtures in the sources' formats (no Internet); the bundled files are
checked for shape and for the provenance records that must travel with them."""
import importlib.util
import json
import unittest
from pathlib import Path

from tests import _env  # noqa: F401
from gps_time_pi import catalog

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "gps_time_pi" / "data"
FIX = Path(__file__).parent / "fixtures" / "sky"

_spec = importlib.util.spec_from_file_location("build_sky_data", ROOT / "tools" / "build_sky_data.py")
sky = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(sky)


class BuilderTest(unittest.TestCase):
    def test_messier_from_openngc(self):
        m = {o["id"]: o for o in sky.messier(FIX, numbers=(1, 22, 31, 40, 101, 102))}
        self.assertEqual(m["M1"], {"id": "M1", "ra": 83.6332, "dec": 22.0145, "type": "supernova remnant",
                                   "mag": 8.4, "names": ["Crab Nebula"], "con": "Tau"})
        self.assertEqual(m["M31"]["mag"], 4.36)                    # no V magnitude: B is used
        self.assertIsNone(m["M22"]["mag"])                         # neither: none, never a guess
        self.assertEqual(m["M31"]["names"], ["Andromeda Galaxy", "Andromeda Nebula"])
        self.assertEqual(m["M40"]["type"], "double star")          # from the addendum

    def test_a_duplicate_takes_the_data_at_its_position_with_a_note(self):
        m = {o["id"]: o for o in sky.messier(FIX, numbers=(101, 102))}
        self.assertEqual((m["M102"]["ra"], m["M102"]["dec"]), (m["M101"]["ra"], m["M101"]["dec"]))
        self.assertEqual(m["M102"]["names"], [])                   # the note is not a searchable name
        self.assertIn("duplicate of M101", m["M102"]["note"])
        self.assertNotIn("note", m["M101"])

    def test_a_missing_messier_number_stops_the_build(self):
        with self.assertRaises(SystemExit):
            sky.messier(FIX, numbers=(2,))

    def test_d3_stars_ra_wraps_to_0_360_and_mag_limit(self):
        s = sky.stars(FIX)
        self.assertEqual(s, [[101.287, -16.716, -1.44], [279.235, 38.784, 0.03], [359.5, 10.123, 3.1]])

    def test_named_stars_are_the_named_ones_to_mag_2_6_brightest_first(self):
        n = sky.named_stars(FIX)
        self.assertEqual([x["id"] for x in n], ["Sirius", "Vega"])
        self.assertEqual(n[1], {"id": "Vega", "ra": 279.2347, "dec": 38.7837, "type": "star",
                                "mag": 0.03, "names": [], "con": "Lyr"})

    def test_constellations_keep_both_serpens_parts(self):
        c = sky.constellations(FIX)
        self.assertEqual([x["id"] for x in c], ["Lyr", "Ser", "Ser"])
        self.assertEqual(c[1]["lines"], [[[236.54, 10.0], [240.0, 12.35]]])


class BundledDataTest(unittest.TestCase):
    def load(self, name):
        return json.loads((DATA / name).read_text(encoding="utf-8"))

    def test_shapes(self):
        m = self.load("messier.json")["messier"]
        self.assertEqual([o["id"] for o in m], [f"M{n}" for n in range(1, 111)])
        cat = self.load("catalog.json")
        self.assertNotIn("messier", cat)                           # CC BY-SA data lives only in messier.json
        self.assertEqual(len(cat["stars"]), 99)
        self.assertEqual(len(self.load("stars.json")), 921)
        self.assertEqual(len(self.load("constellations.json")), 89)
        for o in m + cat["stars"]:
            self.assertTrue(0 <= o["ra"] < 360 and -90 <= o["dec"] <= 90, o["id"])

    def test_every_file_has_its_provenance_and_license_text(self):
        readme = (DATA / "README.md").read_text(encoding="utf-8")
        notices = (ROOT / "THIRD_PARTY_NOTICES.md").read_text(encoding="utf-8")
        for name in ("messier.json", "catalog.json", "stars.json", "constellations.json"):
            self.assertIn(f"`{name}`", readme, name)
            self.assertIn(name, notices, name)
        self.assertIn("CC BY-SA 4.0", readme)
        lic = ROOT / "third_party" / "licenses"
        self.assertIn("Mattia Verga", (lic / "CC-BY-SA-4.0-OpenNGC.txt").read_text(encoding="utf-8"))
        self.assertIn("Olaf Frohn", (lic / "BSD-3-Clause-d3-celestial.txt").read_text(encoding="utf-8"))


class LookupTest(unittest.TestCase):
    def test_lookups(self):
        self.assertEqual(catalog.lookup("M31")["name"], "M31 — Andromeda Galaxy")
        self.assertEqual(catalog.lookup("Pleiades")["id"], "M45")
        self.assertEqual(catalog.lookup("Vega")["con"], "Lyr")
        self.assertIn("duplicate of M101", catalog.lookup("M102")["note"])

    def test_a_note_is_not_a_name(self):
        self.assertIsNone(catalog.lookup("Spindle"))


if __name__ == "__main__":
    unittest.main()
