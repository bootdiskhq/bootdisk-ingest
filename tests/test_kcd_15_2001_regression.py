import json
import unittest
from pathlib import Path


EXPECTED = {
    "schema_version": "0.9",
    "generator_version": "0.9.0",
    "entry_count": 39,
    "disc_file_count": 887,
    "disc_total_size": 630_435_653,
    "disc_manifest_sha256": "98227bf06ce1a59b1e3749578e5beedca7558d23df3b4b49f33c323bc9f421ae",
    "k_dtx_sha256": "a0fa0a2b5b56ce4f4bc4c8114e9b227a951082a4b8d54442a6356d28b9596eef",
    "volume_id": "K_CD_15_2001",
    "logical_block_size": 2048,
    "volume_blocks": 308681,
    "joliet_present": True,
    "joliet_level": 3,
    "joliet_volume_id": "K-CD 15 2001",
    "endianness_mismatches": 0,
}


class Kcd152001RegressionTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        repo_root = Path(__file__).resolve().parents[1]
        manifest_path = repo_root / "manifest.json"

        if not manifest_path.exists():
            raise unittest.SkipTest(
                "manifest.json finnes ikke i repo-roten. "
                "Kjør bootdisk-ingest mot K-CD 15/2001 først."
            )

        with manifest_path.open("r", encoding="utf-8") as fh:
            cls.manifest = json.load(fh)

    def test_version(self):
        self.assertEqual(self.manifest["schema_version"], EXPECTED["schema_version"])
        self.assertEqual(
            self.manifest["generator"]["version"],
            EXPECTED["generator_version"],
        )

    def test_entry_count(self):
        self.assertEqual(len(self.manifest["entries"]), EXPECTED["entry_count"])

    def test_disc_content_identity(self):
        identity = self.manifest["disc"]["content_identity"]
        self.assertEqual(identity["file_count"], EXPECTED["disc_file_count"])
        self.assertEqual(identity["total_size"], EXPECTED["disc_total_size"])
        self.assertEqual(
            identity["manifest_sha256"],
            EXPECTED["disc_manifest_sha256"],
        )

    def test_k_dtx_identity(self):
        self.assertEqual(
            self.manifest["source"]["dtx_file"]["sha256"],
            EXPECTED["k_dtx_sha256"],
        )

    def test_iso9660_metadata(self):
        fs = self.manifest["disc"]["filesystem"]
        pvd = fs["primary_volume_descriptor"]
        joliet = fs["joliet"]

        self.assertEqual(fs["type"], "iso9660")
        self.assertEqual(pvd["volume_id"], EXPECTED["volume_id"])
        self.assertEqual(
            pvd["logical_block_size"]["value"],
            EXPECTED["logical_block_size"],
        )
        self.assertEqual(
            pvd["volume_space_size_blocks"]["value"],
            EXPECTED["volume_blocks"],
        )
        self.assertEqual(joliet["present"], EXPECTED["joliet_present"])
        self.assertEqual(joliet["descriptors"][0]["level"], EXPECTED["joliet_level"])
        self.assertEqual(
            joliet["descriptors"][0]["volume_id"],
            EXPECTED["joliet_volume_id"],
        )
        self.assertEqual(
            len(fs["numeric_endianness_mismatches"]),
            EXPECTED["endianness_mismatches"],
        )


if __name__ == "__main__":
    unittest.main()
