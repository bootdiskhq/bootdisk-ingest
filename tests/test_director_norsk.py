"""Optional qualification of the language cast from K-CD 9/2000."""

import hashlib
import os
from pathlib import Path
import unittest
from bootdisk_ingest.adapters.kcd.director import parse_director_disc


@unittest.skipUnless(os.environ.get("BOOTDISK_DIRECTOR_KCD9_FIXTURES"), "9/2000 not configured")
class NorskTests(unittest.TestCase):
    def test_neotrace_conflict_is_observed_not_repaired(self):
        root = Path(os.environ["BOOTDISK_DIRECTOR_KCD9_FIXTURES"])
        files = []
        expected = [
            "49e4c5b22efe9986e47cea00af31d000022d41cb75699e9d91db53c151a8acb4",
            "06e110f8b7faf1ad1c20073d834c9e3b58afe4d7032ffb6b513a0f086c6764cd",
            "bd3ebb9bf7802d5133fda0584d0690e3187f749769d1ae28338ea8582b4f9b1f",
        ]
        for name, digest in zip(("K-CN.dxr", "Constant.cxt", "Norsk.cxt"), expected):
            data = (root / name).read_bytes()
            self.assertEqual(hashlib.sha256(data).hexdigest(), digest)
            files.append(dict(path=name, size=len(data), sha256=digest))
        result = parse_director_disc(root, {"files": files}, generated_at="fixed")
        entry = next(e for e in result["entries"] if e["source_id"] == "K1D2")
        launches = entry["evidence"]["launches"]
        self.assertEqual(launches["direct"][0]["file"]["path"], "Publisher/Norsk/Setup.exe")
        self.assertEqual(launches["warning_continue"][0]["file"]["path"], "Neotrace/Setup.exe")
        self.assertIn("conflicting_launch_targets", entry["issues"])
        self.assertEqual(
            next(x for x in result["source"]["library_sources"] if x["library"] == 4)[
                "source_path"
            ],
            "Norsk.cxt",
        )
