import hashlib
import tempfile
import unittest
from pathlib import Path
from bootdisk_ingest.core.hashing import sha256_file
from bootdisk_ingest.core.identity import build_content_identity
from bootdisk_ingest.core.inventory import build_directory_inventory


class PreservationTests(unittest.TestCase):
    def test_hash_bytes_and_chunk_boundary(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "bytes"
            path.write_bytes(b"abc" * 100)
            self.assertEqual(sha256_file(path, 7), hashlib.sha256(b"abc" * 100).hexdigest())
            with self.assertRaises(ValueError):
                sha256_file(path, 0)

    def test_identity_order_and_framing(self):
        records = [dict(path="z", size=2, sha256="b" * 64), dict(path="a", size=1, sha256="a" * 64)]
        expected = hashlib.sha256(("a\0" + "a" * 64 + "\nz\0" + "b" * 64 + "\n").encode()).hexdigest()
        self.assertEqual(build_content_identity(records)["manifest_sha256"], expected)
        self.assertEqual(build_content_identity(records), build_content_identity(reversed(records)))
        self.assertEqual(build_content_identity([])["manifest_sha256"], hashlib.sha256(b"").hexdigest())

    def test_missing_root_is_not_empty_inventory(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(ValueError):
                build_directory_inventory(Path(d) / "missing")

    def test_symlink_is_not_silently_followed(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / "real").write_bytes(b"original")
            (root / "link").symlink_to(root / "real")
            with self.assertRaisesRegex(ValueError, "Symbolic links"):
                build_directory_inventory(root)

    def test_case_ambiguity_cannot_choose_an_arbitrary_artifact(self):
        from bootdisk_ingest.core.inventory import FileInventory, FileRecord
        records = [FileRecord("A.exe", 1, "a" * 64), FileRecord("a.exe", 1, "b" * 64)]
        inventory = FileInventory.from_records(records)
        self.assertIs(inventory.find("A.exe")[0], records[0])
        with self.assertRaisesRegex(ValueError, "Ambiguous"):
            inventory.find("A.EXE")

    def test_folder_fallback_does_not_merge_distinct_directories(self):
        from bootdisk_ingest.core.inventory import FileInventory, FileRecord
        records = [FileRecord("App/a", 1, "a" * 64), FileRecord("app/b", 1, "b" * 64)]
        inventory = FileInventory.from_records(records)
        self.assertEqual(inventory.find_folder("App"), [records[0]])
        with self.assertRaisesRegex(ValueError, "Ambiguous"):
            inventory.find_folder("APP")
