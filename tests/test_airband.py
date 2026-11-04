"""Airband bookmarks from the FAA's NASR data (gps_time_pi/airband.py).

No network: the download is injected (an in-memory zip). The FRQ CSV here uses the column names the
code expects (FREQ, FREQ_USE, LAT_DECIMAL, LONG_DECIMAL, SERVICED_FACILITY); the real file's layout is
read by header, and an unknown one is refused, which is tested too. The site is the project's
example location (US Naval Observatory).
"""
import io
import json
import shutil
import tempfile
import unittest
import zipfile
from datetime import date
from pathlib import Path
from unittest import mock

from gps_time_pi import airband as ab

USNO = {"lat": 38.9217, "lon": -77.0669, "alt_msl": 92.0}
HEADER = "EFF_DATE,FACILITY,FAC_NAME,SERVICED_FACILITY,SERVICED_FAC_NAME,LAT_DECIMAL,LONG_DECIMAL,FREQ,FREQ_USE\n"
ROWS = [
    "2026/10/29,DCA,DEMO,DCA,DEMO NATIONAL,38.8521,-77.0377,119.1,LCL/P",          # ~8 km
    "2026/10/29,DCA,DEMO,DCA,DEMO NATIONAL,38.8521,-77.0377,119.1,LCL/P",          # a duplicate row
    "2026/10/29,DCA,DEMO,DCA,DEMO NATIONAL,38.8521,-77.0377,132.65,D-ATIS",
    "2026/10/29,DCA,DEMO,DCA,DEMO NATIONAL,38.8521,-77.0377,257.6,LCL/S",          # UHF: not VHF airband
    "2026/10/29,FAR,FAR,FAR,FAR AWAY,40.6413,-73.7781,119.1,LCL/P",                # ~330 km: outside 80 km
    "2026/10/29,BAD,BAD,BAD,NO FREQ,38.9,-77.0,,LCL/P",
]


def frq_zip(text=HEADER + "\n".join(ROWS) + "\n", name="FRQ.csv"):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr(name, text)
    return buf.getvalue()


class TestCycle(unittest.TestCase):
    def test_28_day_cycles_from_the_faas_anchor(self):
        self.assertEqual(ab.cycle(date(2026, 11, 4)), (date(2026, 10, 29), date(2026, 11, 26)))
        self.assertEqual(ab.cycle(date(2026, 11, 26))[0], date(2026, 11, 26))
        self.assertEqual(ab.cycle(date(2026, 10, 28))[0], date(2026, 10, 1))     # before the anchor
        self.assertEqual(ab.cycle(date(2027, 1, 21))[0], date(2027, 1, 21))

    def test_url_matches_the_faas_listing_whatever_the_locale(self):
        self.assertEqual(ab.url_for(date(2026, 10, 29)),
                         "https://nfdc.faa.gov/webContent/28DaySub/extra/29_Oct_2026_FRQ_CSV.zip")
        self.assertEqual(ab.url_for(date(2027, 1, 21)),
                         "https://nfdc.faa.gov/webContent/28DaySub/extra/21_Jan_2027_FRQ_CSV.zip")


class TestParse(unittest.TestCase):
    def test_vhf_airband_near_the_site_only(self):
        rows = ab.parse_frq(HEADER + "\n".join(ROWS), USNO)
        self.assertEqual([(r["facility"], r["frequency_hz"], r["use"]) for r in rows],
                         [("DCA", 119_100_000, "LCL/P"), ("DCA", 132_650_000, "D-ATIS")])
        self.assertEqual(rows[0]["distance_km"], 8)
        self.assertEqual(rows[0]["source"], "nasr")

    def test_an_unknown_layout_is_refused(self):
        with self.assertRaisesRegex(ab.AirbandError, "no FREQ, LAT_DECIMAL, LONG_DECIMAL column"):
            ab.parse_frq("A,B,C\n1,2,3\n", USNO)

    def test_openwebrx_format(self):
        self.assertEqual(ab.owrx_bookmarks(ab.BUILT_IN)[0], {"name": "Guard (emergency)", "frequency": 121_500_000, "modulation": "am"})


class TestRefresh(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, True)
        for name, value in (("PATH", self.tmp / "airband-bookmarks.json"), ("OWRX_PATH", self.tmp / "airband-openwebrx.json"),
                            ("STATUS_PATH", self.tmp / "airband-refresh.json")):
            p = mock.patch.object(ab, name, value)
            p.start()
            self.addCleanup(p.stop)
        self.urls = []

    def fetch(self, url):
        self.urls.append(url)
        return frq_zip()

    def test_refresh_writes_bookmarks_with_the_cycle(self):
        doc = ab.refresh({"site": USNO, "location_display": "exact"}, today=date(2026, 11, 4), fetch=self.fetch, now=1_793_800_000)
        self.assertEqual(self.urls, ["https://nfdc.faa.gov/webContent/28DaySub/extra/29_Oct_2026_FRQ_CSV.zip"])
        self.assertEqual(doc["nasr_cycle"], "2026-10-29")
        self.assertEqual(len(doc["bookmarks"]), 2)
        owrx = json.loads((self.tmp / "airband-openwebrx.json").read_text())
        self.assertEqual(len(owrx), len(ab.BUILT_IN) + 2)
        saved = (self.tmp / "airband-bookmarks.json").read_text()
        self.assertNotIn("38.9217", saved)                                # the site itself is never written
        self.assertNotIn("-77.0669", saved)

    def test_rounded_mode_filters_from_the_rounded_site(self):
        doc = ab.refresh({"site": USNO, "location_display": "rounded"}, today=date(2026, 11, 4), fetch=self.fetch)
        self.assertEqual(doc["site_precision"], "rounded")

    def test_hidden_mode_fetches_nothing(self):
        with self.assertRaisesRegex(ab.AirbandError, "hidden privacy mode"):
            ab.refresh({"site": USNO, "location_display": "hidden"}, fetch=self.fetch)
        self.assertEqual(self.urls, [])
        self.assertFalse((self.tmp / "airband-bookmarks.json").exists())

    def test_a_bad_download_keeps_the_previous_bookmarks(self):
        ab.refresh({"site": USNO}, today=date(2026, 11, 4), fetch=self.fetch)
        before = (self.tmp / "airband-bookmarks.json").read_text()
        for bad in (lambda url: b"not a zip", lambda url: frq_zip(name="OTHER.csv"), lambda url: frq_zip("A,B\n1,2\n")):
            with self.subTest(bad=bad):
                with self.assertRaises(ab.AirbandError):
                    ab.refresh({"site": USNO}, today=date(2026, 11, 26), fetch=bad)
                self.assertEqual((self.tmp / "airband-bookmarks.json").read_text(), before)

    def test_status_flags_a_cycle_past_28_days(self):
        ab.refresh({"site": USNO}, today=date(2026, 11, 4), fetch=self.fetch)
        st = ab.status({}, today=date(2026, 11, 10))
        self.assertEqual((st["nasr"]["cycle"], st["nasr"]["stale"], st["nasr"]["age_days"]["value"]), ("2026-10-29", False, 12))
        st = ab.status({}, today=date(2026, 11, 27))
        self.assertTrue(st["nasr"]["stale"])
        self.assertEqual(st["current_cycle"], "2026-11-26")
        self.assertFalse(ab.status({"location_display": "hidden"})["refresh_allowed"])

    def test_no_set_yet_is_built_ins_only(self):
        st = ab.status({})
        self.assertIsNone(st["nasr"])
        self.assertEqual([b["frequency_hz"] for b in st["built_in"]], [121_500_000, 122_750_000, 123_025_000, 122_900_000])

    def test_main_records_a_failure(self):
        with mock.patch.object(ab, "refresh", side_effect=ab.AirbandError("download failed: nope")):
            self.assertEqual(ab.main(["refresh"]), 1)
        last = json.loads((self.tmp / "airband-refresh.json").read_text())
        self.assertFalse(last["ok"])
        self.assertIn("download failed", last["error"])


class TestWiring(unittest.TestCase):
    ROOT = Path(__file__).resolve().parents[1]

    def test_the_web_service_never_fetches(self):
        server = (self.ROOT / "gps_time_pi" / "server.py").read_text(encoding="utf-8")
        self.assertIn("airband.status(config.load())", server)
        self.assertNotIn("airband.refresh", server)
        from gps_time_pi import system
        self.assertEqual(system.ACTIONS["refresh_airband"], ["systemctl", "start", "--no-block", "gps-time-airband-fetch.service"])

    def test_the_unit_runs_as_the_web_services_user_and_is_never_timed(self):
        u = (self.ROOT / "system" / "gps-time-airband-fetch.service").read_text(encoding="utf-8")
        self.assertIn("User=gps-time", u)
        self.assertIn("Type=oneshot", u)
        self.assertIn("ReadWritePaths=/opt/gps-time-pi", u)
        self.assertNotIn("[Install]", u)
        self.assertNotIn("OnCalendar", u)

    def test_websdr_installs_it_and_links_openwebrx_bookmarks(self):
        s = (self.ROOT / "scripts" / "websdr.sh").read_text(encoding="utf-8")
        self.assertIn('install -m 0644 "$SRC/gps-time-airband-fetch.service"', s)
        self.assertIn('ln -sfn /opt/gps-time-pi/airband-openwebrx.json "$ROOT/etc/openwebrx/bookmarks.d/gps-time-airband.json"', s)


if __name__ == "__main__":
    unittest.main()
