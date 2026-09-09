import tempfile
import unittest
from pathlib import Path
from bootdisk_ingest.iso9660 import inspect_iso9660, _parse_volume_datetime


def descriptor(kind):
    block = bytearray(2048)
    block[0] = kind
    block[1:6] = b"CD001"
    block[6] = 1
    return block


class IsoTests(unittest.TestCase):
    def inspect(self, *blocks):
        with tempfile.TemporaryDirectory() as d:
            image = Path(d) / "test.iso"
            image.write_bytes(bytes(16 * 2048) + b"".join(blocks))
            return inspect_iso9660(image)

    def test_primary_joliet_and_terminator_from_bytes(self):
        primary = descriptor(1)
        primary[40:72] = b"TEST".ljust(32, b" ")
        primary[128:132] = (2048).to_bytes(2, "little") + (2048).to_bytes(2, "big")
        joliet = descriptor(2)
        joliet[88:91] = b"%/E"
        joliet[40:72] = "Test".ljust(16).encode("utf-16-be")
        fs = self.inspect(primary, joliet, descriptor(255))
        self.assertTrue(fs["terminator_seen"])
        self.assertEqual(fs["descriptor_count"], 3)
        self.assertEqual(fs["primary_volume_descriptor"]["volume_id"], "TEST")
        self.assertEqual(fs["primary_volume_descriptor"]["logical_block_size"]["value"], 2048)
        self.assertEqual(fs["joliet"]["descriptors"][0]["volume_id"], "Test")
        self.assertEqual(fs["joliet"]["descriptors"][0]["level"], 3)

    def test_endian_conflict_retains_both_observations(self):
        primary = descriptor(1)
        primary[128:132] = (2048).to_bytes(2, "little") + (1024).to_bytes(2, "big")
        fs = self.inspect(primary)
        value = fs["primary_volume_descriptor"]["logical_block_size"]
        self.assertIsNone(value["value"])
        self.assertEqual((value["little_endian"], value["big_endian"]), (2048, 1024))
        self.assertEqual(fs["numeric_endianness_mismatches"], ["logical_block_size"])
        self.assertFalse(fs["terminator_seen"])

    def test_truncated_and_unknown_images(self):
        self.assertFalse(self.inspect(b"CD001")["iso9660"])
        self.assertFalse(self.inspect(bytes(2048))["iso9660"])
        fs = self.inspect(descriptor(1), bytes(2048))
        self.assertEqual(fs["descriptor_count"], 1)
        self.assertFalse(fs["terminator_seen"])
        self.assertEqual(inspect_iso9660(None), {"available": False})

    def test_dates_keep_invalid_and_unspecified_values(self):
        self.assertEqual(_parse_volume_datetime(b"0000000000000000\0")["interpretation"], "unspecified")
        self.assertFalse(_parse_volume_datetime(b"2000130123595900\0")["valid"])
        parsed = _parse_volume_datetime(b"2000010223595912\x04")
        self.assertEqual(parsed["iso8601"], "2000-01-02T23:59:59.120+01:00")
        self.assertFalse(_parse_volume_datetime(b"bad")["valid"])
