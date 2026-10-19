"""get_throttled decoding (system.decode_throttled): each condition, now and latched since
boot. Shown on /app/ Administration → Power (parity item 21)."""
import unittest

from tests import _env  # noqa: F401
from gps_time_pi import system


class DecodeThrottledTest(unittest.TestCase):
    def flags(self, raw):
        return {f["label"]: f["active"] for f in system.decode_throttled(raw)["flags"]}

    def test_all_clear(self):
        d = system.decode_throttled("0x0")
        self.assertFalse(d["any_now"] or d["any_ever"])
        self.assertEqual(len(d["flags"]), 8)
        self.assertFalse(any(self.flags("0x0").values()))

    def test_under_voltage_now_and_since_boot(self):
        f = self.flags("0x50005")
        self.assertTrue(f["Under-voltage now"])
        self.assertTrue(f["Throttled now"])
        self.assertTrue(f["Under-voltage occurred since boot"])
        self.assertTrue(f["Throttled since boot"])
        self.assertFalse(f["Frequency capped now"])

    def test_latched_only(self):
        d = system.decode_throttled("0x50000")
        self.assertFalse(d["any_now"])
        self.assertTrue(d["any_ever"])
        self.assertTrue(self.flags("0x50000")["Under-voltage occurred since boot"])

    def test_now_flag_marks_the_low_bits(self):
        for f in system.decode_throttled("0xf000f")["flags"]:
            self.assertTrue(f["active"])
            self.assertEqual(f["now"], f["label"].endswith(" now"))

    def test_bad_value_raises_for_the_caller(self):
        with self.assertRaises(ValueError):
            system.decode_throttled("zz")


if __name__ == "__main__":
    unittest.main()
