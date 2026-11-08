"""Tests for einkctl without hardware: a fake USB device records what would go over the wire.

Run: python3 -m unittest discover -s tests
"""
import importlib.machinery
import importlib.util
import os
import struct
import unittest

HERE = os.path.dirname(__file__)
loader = importlib.machinery.SourceFileLoader("einkctl", os.path.join(HERE, "..", "einkctl"))
spec = importlib.util.spec_from_loader("einkctl", loader)
einkctl = importlib.util.module_from_spec(spec)
loader.exec_module(einkctl)

CSW_OK = struct.pack("<IIIB", 0x53425355, einkctl.TAG, 0, 0)


class FakeDevice:
    """Answers every CBW with a good CSW; `replies` queues data-phase reads."""

    def __init__(self, replies=()):
        self.writes = []
        self.replies = list(replies)

    def write(self, ep, data, timeout):
        self.writes.append((ep, bytes(data)))

    def read(self, ep, length, timeout):
        if length == 13:
            return CSW_OK
        return self.replies.pop(0)

    def cbws(self):
        return [d for _, d in self.writes if d[:4] == b"USBC"]

    def payloads(self):
        return [d for _, d in self.writes if d[:4] != b"USBC"]


class Framing(unittest.TestCase):

    def test_cbw_is_31_bytes_with_signature_tag_and_direction(self):
        c = einkctl.cbw(b"\x12", einkctl.DIR_IN, 0x28)
        self.assertEqual(len(c), 31)
        sig, tag, length, flags, lun, cblen = struct.unpack_from("<IIIBBB", c)
        self.assertEqual((sig, tag, length, flags, lun, cblen),
                         (0x43425355, 0x89518961, 0x28, 0x80, 0, 16))
        self.assertEqual(c[15:], b"\x12".ljust(16, b"\0"))

    def test_bad_csw_raises(self):
        with self.assertRaises(RuntimeError):
            einkctl.check_csw(struct.pack("<IIIB", 0x53425355, 0, 0, 1))
        with self.assertRaises(RuntimeError):
            einkctl.check_csw(struct.pack("<IIIB", 0xDEADBEEF, 0, 0, 0))

    def test_mailbox_arguments_start_at_byte_4(self):
        # Regression: packing arguments from byte 2 made "set mode 2" arrive as mode 1.
        p = einkctl.mailbox_payload(0x61, 2, 1)
        self.assertEqual(len(p), 0x24)
        self.assertEqual(struct.unpack_from("<HHHH", p), (0x61, 0, 2, 1))


class Commands(unittest.TestCase):

    def test_set_mode_sends_mailbox_0x61_with_mode_and_flag(self):
        dev = FakeDevice()
        einkctl.Tcon(dev).set_mode(2)
        (c,) = dev.cbws()
        self.assertEqual(c[15:22], bytes([0xFE, 0, 0, 0, 0, 0, 0xA8]))
        self.assertEqual(c[12], einkctl.DIR_OUT)
        (p,) = dev.payloads()
        self.assertEqual(struct.unpack_from("<HHHH", p), (0x61, 0, 2, 1))

    def test_get_mode_reads_mailbox_0x60(self):
        dev = FakeDevice(replies=[struct.pack("<HH", 240, 0)])
        self.assertEqual(einkctl.Tcon(dev).get_mode(), 240)
        write_cbw, read_cbw = dev.cbws()
        self.assertEqual(struct.unpack_from("<H", dev.payloads()[0])[0], 0x60)
        self.assertEqual(read_cbw[15:25], bytes([0xFE, 0, 0, 0, 0, 0, 0xA9, 0, 0, 4]))
        self.assertEqual(read_cbw[12], einkctl.DIR_IN)

    def test_refresh_returns_to_previous_mode(self):
        dev = FakeDevice(replies=[struct.pack("<HH", 0, 0)])
        back = einkctl.refresh(einkctl.Tcon(dev), sleep=lambda s: None)
        self.assertEqual(back, 0)
        modes = [struct.unpack_from("<HHH", p)[2] for p in dev.payloads()[1:]]
        self.assertEqual(modes, [17, 0])

    def test_refresh_with_then_skips_reading_the_mode(self):
        dev = FakeDevice()
        einkctl.refresh(einkctl.Tcon(dev), then=2, sleep=lambda s: None)
        modes = [struct.unpack_from("<HHH", p)[2] for p in dev.payloads()]
        self.assertEqual(modes, [17, 2])

    def test_refresh_stuck_in_refresh_falls_back_to_default(self):
        dev = FakeDevice(replies=[struct.pack("<HH", 17, 0)])
        back = einkctl.refresh(einkctl.Tcon(dev), sleep=lambda s: None)
        self.assertEqual(back, einkctl.DEFAULT_MODE)


class Parsing(unittest.TestCase):

    def test_names_and_numbers(self):
        self.assertEqual(einkctl.parse_mode("browser"), 2)
        self.assertEqual(einkctl.parse_mode("240"), 240)
        self.assertEqual(einkctl.parse_mode("0xf0"), 240)

    def test_unknown_name_is_rejected(self):
        with self.assertRaises(Exception):
            einkctl.parse_mode("turbo")

    def test_only_vetted_mailbox_commands(self):
        # Flash, VCOM, PMIC and power-sequence commands stay out; a new MB_ needs a review.
        codes = {v for k, v in vars(einkctl).items() if k.startswith("MB_")}
        self.assertEqual(codes, {0x60, 0x61})


if __name__ == "__main__":
    unittest.main()
