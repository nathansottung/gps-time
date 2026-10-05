"""chrony polling the station's own address (e.g. DHCP names the station as the
LAN's NTP server) is never an external reference, whatever stratum it shows."""

import unittest
from pathlib import Path
from unittest import mock

from tests import _env  # noqa: F401
from gps_time_pi import chrony, timing_chain as tc
from tests.test_timing_chain import REFCFG, gnss_no_signal, gnss_ok

FIX = Path(__file__).parent / "fixtures" / "chrony"
SELF = frozenset({"192.0.2.50", "127.0.0.1", "::1", "2001:db8::50"})

IP_ADDR = """\
1: lo    inet 127.0.0.1/8 scope host lo\\       valid_lft forever preferred_lft forever
1: lo    inet6 ::1/128 scope host noprefixroute \\       valid_lft forever preferred_lft forever
2: eth0    inet 192.0.2.50/24 brd 192.0.2.255 scope global dynamic noprefixroute eth0\\       valid_lft 80000sec
2: eth0    inet6 2001:DB8::50/64 scope global dynamic noprefixroute \\       valid_lft 80000sec
2: eth0    inet6 fe80::1234%eth0/64 scope link noprefixroute \\       valid_lft forever preferred_lft forever
"""


def rows(fixture, addrs=SELF):
    return chrony.parse_sources((FIX / f"{fixture}.txt").read_text(), local_addrs=addrs)


def trk(fixture):
    return chrony.parse_tracking((FIX / f"{fixture}.txt").read_text())


class TestLocalAddresses(unittest.TestCase):
    def test_parse_ip_addr(self):
        self.assertEqual(chrony.parse_ip_addr(IP_ADDR),
                         {"127.0.0.1", "::1", "192.0.2.50", "2001:db8::50", "fe80::1234"})

    def test_without_ip_only_loopback_is_known(self):
        with mock.patch.dict(chrony._LOCAL_ADDRS, {"at": 0.0, "addrs": frozenset()}), \
             mock.patch.object(chrony.subprocess, "run", side_effect=FileNotFoundError("ip")):
            self.assertEqual(chrony.local_addresses(), frozenset({"127.0.0.1", "::1", "localhost"}))

    def test_cached(self):
        fake = mock.Mock(return_value=mock.Mock(returncode=0, stdout=IP_ADDR))
        with mock.patch.dict(chrony._LOCAL_ADDRS, {"at": 0.0, "addrs": frozenset()}), \
             mock.patch.object(chrony.subprocess, "run", fake):
            self.assertIn("192.0.2.50", chrony.local_addresses())
            chrony.local_addresses()
            self.assertEqual(fake.call_count, 1)
            self.assertEqual(fake.call_args[0][0], ["ip", "-o", "addr", "show"])


class TestMarking(unittest.TestCase):
    def test_own_address_is_marked_and_others_are_not(self):
        by = {r["name"]: r for r in rows("sources_self_selected")}
        self.assertTrue(by["192.0.2.50"]["is_self"])
        self.assertFalse(by["198.51.100.7"]["is_self"])
        self.assertFalse(by["GPS"]["is_self"])

    def test_a_refclock_is_never_self(self):
        by = {r["name"]: r for r in rows("sources_pps_selected", addrs=frozenset({"gps", "nmea"}))}
        self.assertFalse(by["GPS"]["is_self"])

    def test_not_self_on_another_machine(self):
        self.assertFalse(any(r["is_self"] for r in rows("sources_self_selected", addrs=frozenset({"127.0.0.1"}))))


class TestStatus(unittest.TestCase):
    def test_selecting_itself_is_holdover_not_a_network_reference(self):
        for g in (gnss_ok(), gnss_no_signal()):
            st = tc.timing_status(trk("tracking_network"), rows("sources_self_selected"), gnss=g, refclocks=REFCFG)
            self.assertEqual(st["code"], "HOLDOVER")
            self.assertEqual(st["banner"], "HOLDOVER · NO EXTERNAL REFERENCE · CHRONY SELECTED THIS STATION ITSELF")
            self.assertNotIn("SYNCHRONIZED", st["banner"])
            self.assertNotIn("NETWORK FAILOVER", st["banner"])
            self.assertIn("192.0.2.50", st["detail"])
            self.assertTrue(st["source"]["is_self"])

    def test_same_sources_on_another_machine_are_an_ordinary_network_source(self):
        st = tc.timing_status(trk("tracking_network"), rows("sources_self_selected", addrs=frozenset()),
                              gnss=gnss_no_signal(), refclocks=REFCFG)
        self.assertEqual(st["code"], "NETWORK_FAILOVER")

    def test_listed_but_not_selected_does_not_change_a_gps_pps_status(self):
        st = tc.timing_status(trk("tracking_pps"), rows("sources_self_listed"), gnss=gnss_ok(), refclocks=REFCFG)
        self.assertEqual(st["code"], "GPS_PPS")


class TestChronyView(unittest.TestCase):
    def view(self, fixture):
        inputs = {"sources_ok": True, "sources_text": (FIX / f"{fixture}.txt").read_text(),
                  "tracking_ok": True, "tracking_text": (FIX / "tracking_network.txt").read_text()}
        with mock.patch.object(chrony, "local_addresses", lambda: SELF):
            return tc.chrony_view(inputs, REFCFG)

    def test_selected_self_is_flagged(self):
        cv = self.view("sources_self_selected")
        self.assertTrue(cv["selected"]["is_self"])
        self.assertEqual(cv["self_sources"], ["192.0.2.50"])

    def test_listed_self_is_reported(self):
        cv = self.view("sources_self_listed")
        self.assertFalse(cv["selected"]["is_self"])
        self.assertTrue(cv["selected"]["is_pps"])
        self.assertEqual(cv["self_sources"], ["192.0.2.50"])

    def test_no_self_sources_normally(self):
        self.assertEqual(self.view("sources_failover")["self_sources"], [])


if __name__ == "__main__":
    unittest.main()
