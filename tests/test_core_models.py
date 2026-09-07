import unittest
import tempfile
from pathlib import Path
from bootdisk_ingest.core.identity import build_content_identity
from bootdisk_ingest.core.identity import artifact_id_from_sha256
from bootdisk_ingest.core.models import Artifact
from bootdisk_ingest.core.provenance import occurrence_for_artifact
from bootdisk_ingest.core.inventory import FileRecord
from bootdisk_ingest.core.inventory import (
        FileRecord,
        build_directory_inventory,
)
from bootdisk_ingest.inventory import get_file_record
from bootdisk_ingest.core.inventory import (
    FileInventory,
    FileRecord,
    build_directory_inventory,
)
from bootdisk_ingest.inventory import (
        get_file_record,
        get_folder_records,
)

class CoreModelTests(unittest.TestCase):
    def test_standalone_artifact_requires_no_magazine_context(self):
        digest = "a" * 64
        artifact = Artifact(
            artifact_id=artifact_id_from_sha256(digest),
            sha256=digest,
            filename="example.exe",
        )
        occurrence = occurrence_for_artifact(artifact, path="example.exe")
        self.assertEqual(artifact.artifact_id, f"sha256:{digest}")
        self.assertIsNone(occurrence.source_id)
        self.assertIsNone(occurrence.media_id)
        self.assertIsNone(occurrence.entry_id)

    def test_file_record_is_source_agnostic(self):
        record = FileRecord(
                path="Games/Doom/setup.exe",
                size=123456,
                sha256="a" * 64,
        )
        self.assertEqual(record.path, "Games/Doom/setup.exe")
        self.assertEqual(record.size, 123456)
        self.assertEqual(record.sha256, "a" * 64)

    def test_content_identity_matches_for_dict_and_file_record(self):
        dict_records = [
         {
             "path": "A/file1.exe",
             "size": 100,
             "sha256": "a" * 64,
         },
         {
             "path": "B/file2.dll",
             "size": 200,
             "sha256": "b" * 64,
         },
        ]

        model_records = [
            FileRecord(
             path="A/file1.exe",
             size=100,
             sha256="a" * 64,
            ),
            FileRecord(
             path="B/file2.dll",
             size=200,
             sha256="b" * 64,
            ),
        ]

        dict_identity = build_content_identity(dict_records)
        model_identity = build_content_identity(model_records)

        self.assertEqual(dict_identity, model_identity)

    def test_directory_inventory_returns_file_records(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)

            (root / "Games").mkdir()
            (root / "Games" / "game.exe").write_bytes(b"game")
            (root / "readme.txt").write_bytes(b"hello")

            records = build_directory_inventory(root)

            self.assertEqual(len(records), 2)
            self.assertTrue(all(isinstance(record, FileRecord) for record in records))

            self.assertEqual(
                    [record.path for record in records],
                    [
                        "Games/game.exe",
                        "readme.txt",
                    ],
            )

    def test_file_lookup_falls_back_to_case_insensitive_match(self):
        """File lookup should preserve the requested path and report case mismatch."""

        actual_record = {
            "path": "Tools/Foo/setup.exe",
            "size": 1234,
            "sha256": "a" * 64,
        }

        inventory = {
            "files": [actual_record],
            "by_path": {
             actual_record["path"]: actual_record,
            },
            "by_casefold_path": {
                actual_record["path"].casefold(): actual_record,
            },
        }

        requested_path = "TOOLS/FOO/SETUP.EXE"

        result = get_file_record(
            inventory,
            requested_path,
        )

        # The source-provided path must be preserved even when its casing does not
        # match the path actually observed in the filesystem.
        self.assertEqual(
            result["path"],
            requested_path,
        )

        self.assertTrue(result["exists"])
        self.assertTrue(result["is_file"])

        # The observed filesystem path is recorded separately so preservation does
        # not silently rewrite the source metadata.
        self.assertEqual(
            result["resolved_path"],
            actual_record["path"],
        )

        # Make the reason for resolved_path explicit in the resulting metadata.
        self.assertTrue(
            result["path_case_mismatch"]
        )

        # A case-insensitive lookup must still return the preservation observations
        # belonging to the actual file that was found.
        self.assertEqual(
            result["size"],
            actual_record["size"],
        )
        self.assertEqual(
            result["sha256"],
            actual_record["sha256"],
        )

    def test_file_inventory_builds_lookup_indexes(self):
        """FileInventory should support exact and case-insensitive path lookup."""

        first = FileRecord(
            path="Tools/Foo/setup.exe",
            size=100,
            sha256="a" * 64,
        )

        second = FileRecord(
            path="Games/Doom/doom.exe",
            size=200,
            sha256="b" * 64,
        )

        inventory = FileInventory.from_records(
            [first, second]
        )

        # Exact paths must resolve to the original FileRecord objects.
        self.assertIs(
            inventory.by_path["Tools/Foo/setup.exe"],
            first,
        )

        self.assertIs(
            inventory.by_path["Games/Doom/doom.exe"],
            second,
        )

        # A case-folded lookup index allows source metadata with different casing
        # to resolve without modifying the preserved path itself.
        self.assertIs(
            inventory.by_casefold_path[
                "TOOLS/FOO/SETUP.EXE".casefold()
            ],
            first,
        )
    def test_file_inventory_find_reports_case_mismatch(self):
        """FileInventory.find should distinguish exact and folded path matches."""

        record = FileRecord(
            path="Tools/Foo/setup.exe",
            size=1234,
            sha256="a" * 64,
        )

        inventory = FileInventory.from_records([record])

        # An exact path should resolve without reporting a mismatch.
        exact_match, exact_mismatch = inventory.find(
            "Tools/Foo/setup.exe"
        )

        self.assertIs(exact_match, record)
        self.assertFalse(exact_mismatch)

        # Different casing should resolve to the same preserved observation while
        # explicitly reporting that case-insensitive fallback was required.
        folded_match, folded_mismatch = inventory.find(
            "TOOLS/FOO/SETUP.EXE"
        )

        self.assertIs(folded_match, record)
        self.assertTrue(folded_mismatch)

        # A genuinely unknown path must remain unresolved.
        missing_match, missing_mismatch = inventory.find(
            "Tools/Foo/missing.exe"
        )

        self.assertIsNone(missing_match)
        self.assertFalse(missing_mismatch)

    def test_folder_lookup_falls_back_to_case_insensitive_match(self):
        """Folder lookup should preserve legacy case-insensitive behaviour."""

        files = [
            {
                "path": "Tools/Foo/setup.exe",
                "size": 100,
                "sha256": "a" * 64,
            },
            {
                "path": "Tools/Foo/readme.txt",
                "size": 200,
                "sha256": "b" * 64,
            },
            {
                "path": "Games/Bar/game.exe",
                "size": 300,
                "sha256": "c" * 64,
            },
        ]

        inventory = {
            "files": files,
        }

        result = get_folder_records(
            inventory,
            "TOOLS/FOO",
        )

        # Different casing in source metadata should still resolve to the
        # observed folder contents without including unrelated files.
        self.assertEqual(
            [item["path"] for item in result],
            [
                "Tools/Foo/setup.exe",
                "Tools/Foo/readme.txt",
            ],
        )   

    def test_file_inventory_find_folder_falls_back_to_case_insensitive_match(self):
        """FileInventory should support case-insensitive folder resolution."""

        records = [
            FileRecord(
                path="Tools/Foo/setup.exe",
                size=100,
                sha256="a" * 64,
            ),
            FileRecord(
                path="Tools/Foo/readme.txt",
                size=200,
                sha256="b" * 64,
            ),
            FileRecord(
                path="Games/Bar/game.exe",
                size=300,
                sha256="c" * 64,
            ),
        ]

        inventory = FileInventory.from_records(records)

        result = inventory.find_folder("TOOLS/FOO")

        # The requested casing differs from the observed filesystem, but only
        # records belonging to the matching folder should be returned.
        self.assertEqual(
            [record.path for record in result],
            [
                "Tools/Foo/setup.exe",
                "Tools/Foo/readme.txt",
            ],
        )   



if __name__ == "__main__":
    unittest.main()
