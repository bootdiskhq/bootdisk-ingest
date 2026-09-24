"""Execute algorithms on historical observations; this is not a media re-ingest."""
import json
import os
from pathlib import Path
import unittest
from bootdisk_ingest.adapters.kcd.parser import build_entry
from bootdisk_ingest.core.identity import build_content_identity
from bootdisk_ingest.stats import build_statistics
from bootdisk_ingest.validation import build_validation
from bootdisk_ingest.pipeline import ingest_kcd

BASELINE = Path(__file__).resolve().parents[1] / "manifest.json"


class ReferenceExecutionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.reference = json.loads(BASELINE.read_text(encoding="utf-8"))

    def test_recalculate_global_and_entry_identities(self):
        m = self.reference
        self.assertEqual(build_content_identity(m["file_inventory"]), m["disc"]["content_identity"])
        files = {f["path"]: f for f in m["file_inventory"]}
        for entry in m["entries"]:
            with self.subTest(entry=entry["source_id"]):
                self.assertEqual(build_content_identity([files[x] for x in entry["files"]["inventory_refs"]]), entry["content_identity"])

    def test_execute_entry_projection_statistics_and_validation(self):
        m = self.reference
        inventory = {"files": m["file_inventory"]}
        rebuilt = [build_entry(inventory, e["source_id"], e["raw"]) for e in m["entries"]]
        self.assertEqual(rebuilt, m["entries"])
        self.assertEqual(build_statistics(rebuilt, inventory), m["statistics"])
        self.assertEqual(build_validation(rebuilt), m["validation"])


@unittest.skipUnless(os.environ.get("BOOTDISK_KCD_ROOT"), "Real K-CD media not configured")
class RealMediaTests(unittest.TestCase):
    def test_ingest_reference_media(self):
        expected = json.loads(BASELINE.read_text(encoding="utf-8"))
        result = ingest_kcd(os.environ["BOOTDISK_KCD_ROOT"], image=os.environ.get("BOOTDISK_KCD_IMAGE"))
        # The frozen 39-entry fixture covers K.DTX only. Keep those exact checks,
        # then independently require the newly observed Tools catalogue.
        primary = [e for e in result["entries"] if e["source_id"].startswith("K")]
        self.assertEqual(primary, expected["entries"])
        self.assertEqual(result["file_inventory"], expected["file_inventory"])
        self.assertEqual(build_statistics(primary, {"files": result["file_inventory"]}), expected["statistics"])
        self.assertEqual(build_validation(primary), expected["validation"])
        tools = [e for e in result["entries"] if e["source_id"].startswith("I")]
        self.assertEqual(len(result["entries"]), 68)
        self.assertEqual(len(tools), 29)
        self.assertTrue(all(e["evidence"]["description_tools"]["text"] for e in tools))
        self.assertTrue(all(e["files"]["discovered"]["screenshot"]["exists"] for e in tools))
        self.assertTrue(all(e["files"]["referenced"]["installer"]["exists"] for e in tools))
        self.assertEqual(result["source"]["supplemental_metadata"][0]["sha256"],
                         "05049722c88b4851949bc9431496ea959793f948b9f89605a13174da5b9c4409")
        self.assertIn({"folder": "tools/cpuz", "entry_ids": ["K23", "I2"],
                       "meaning": "shared folder, not an identity decision"},
                      result["source"]["coverage"]["shared_entry_folders"])
        self.assertEqual(result["disc"]["content_identity"], expected["disc"]["content_identity"])
        self.assertEqual(result["source"]["dtx_file"]["sha256"], expected["source"]["dtx_file"]["sha256"])
        if os.environ.get("BOOTDISK_KCD_IMAGE"):
            self.assertEqual(result["media"], expected["media"])
            self.assertEqual(result["disc"]["filesystem"], expected["disc"]["filesystem"])
