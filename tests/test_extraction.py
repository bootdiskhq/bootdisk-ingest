import hashlib
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from bootdisk_ingest.extraction import extract_entries


class ExtractionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name) / "source"
        self.root.mkdir()
        (self.root / "Setup.exe").write_bytes(b"fixture, never executed")
        self.dest = Path(self.tmp.name) / "export"
        record = {
            "path": "Setup.exe",
            "size": 23,
            "sha256": hashlib.sha256(b"fixture, never executed").hexdigest(),
        }
        record["size"] = (self.root / "Setup.exe").stat().st_size
        self.manifest = {
            "disc": {},
            "source": {},
            "file_inventory": [record],
            "entries": [
                {
                    "source_id": "K1D2",
                    "normalized": {"title": "Example"},
                    "files": {"inventory_refs": ["Setup.exe"]},
                    "issues": ["conflicting_launch_targets"],
                }
            ],
        }

    def test_copies_bytes_and_preserves_conflict_and_metadata(self):
        result = extract_entries(self.root, self.manifest, self.dest)
        self.assertEqual(
            (self.dest / "0001/files/Setup.exe").read_bytes(),
            (self.root / "Setup.exe").read_bytes(),
        )
        entry = json.loads((self.dest / "0001/entry.json").read_text())
        self.assertEqual(entry, self.manifest["entries"][0])
        self.assertEqual(result["entries"][0]["issues"], ["conflicting_launch_targets"])
        self.assertTrue((self.dest / "extraction.json").exists())

    def test_explicit_discovered_file_is_preserved_even_when_not_inventory_ref(self):
        shot = self.root / "Shot.jpg"
        shot.write_bytes(b"observed screenshot")
        shot_record = {
            "path": "Shot.jpg",
            "size": shot.stat().st_size,
            "sha256": hashlib.sha256(shot.read_bytes()).hexdigest(),
        }
        self.manifest["file_inventory"].append(shot_record)
        self.manifest["entries"][0]["files"]["discovered"] = {
            "screenshot": {
                "exists": True,
                "is_file": True,
                "path": "Shot.jpg",
                "size": shot_record["size"],
                "sha256": shot_record["sha256"],
            }
        }

        result = extract_entries(self.root, self.manifest, self.dest)

        self.assertEqual((self.dest / "0001/files/Shot.jpg").read_bytes(), shot.read_bytes())
        self.assertEqual(
            {record["path"] for record in result["entries"][0]["copied_files"]},
            {"Setup.exe", "Shot.jpg"},
        )

    def test_discovered_nonfile_is_not_promoted_to_extraction_reference(self):
        self.manifest["entries"][0]["files"]["discovered"] = {
            "folder": {
                "exists": True,
                "is_file": False,
                "path": "NeighborFolder",
            }
        }

        result = extract_entries(self.root, self.manifest, self.dest)

        self.assertEqual(
            [record["path"] for record in result["entries"][0]["copied_files"]],
            ["Setup.exe"],
        )

    def test_existing_destination_is_preserved(self):
        self.dest.mkdir()
        (self.dest / "keep").write_text("keep")
        with self.assertRaises(FileExistsError):
            extract_entries(self.root, self.manifest, self.dest)
        self.assertTrue((self.dest / "keep").exists())

    def test_changed_bytes_fail_and_remove_partial_export(self):
        (self.root / "Setup.exe").write_bytes(b"changed")
        with self.assertRaisesRegex(ValueError, "changed"):
            extract_entries(self.root, self.manifest, self.dest)
        self.assertFalse(self.dest.exists())

    def test_traversal_rejected_before_destination_created(self):
        self.manifest["entries"][0]["files"]["inventory_refs"] = ["../secret"]
        with self.assertRaises(ValueError):
            extract_entries(self.root, self.manifest, self.dest)
        self.assertFalse(self.dest.exists())

    def test_symlink_rejected(self):
        (self.root / "Setup.exe").unlink()
        outside = Path(self.tmp.name) / "outside"
        outside.write_bytes(b"fixture, never executed")
        (self.root / "Setup.exe").symlink_to(outside)
        with self.assertRaises(ValueError):
            extract_entries(self.root, self.manifest, self.dest)

    def test_source_destination_overlap_rejected(self):
        with self.assertRaises(ValueError):
            extract_entries(self.root, self.manifest, self.root / "export")

    def test_empty_reference_keeps_entry_for_review(self):
        self.manifest["entries"][0]["files"]["inventory_refs"] = []
        result = extract_entries(self.root, self.manifest, self.dest)
        self.assertEqual(result["entries"][0]["copied_files"], [])
        self.assertTrue((self.dest / "0001/entry.json").exists())

    def test_cli_extracts_even_when_strict_reports_metadata_issues(self):
        from unittest.mock import patch
        from bootdisk_ingest.cli import main

        self.manifest["validation"] = {"valid": False}
        output = Path(self.tmp.name) / "manifest.json"
        with patch("bootdisk_ingest.cli.ingest_kcd", return_value=self.manifest):
            status = main(
                [
                    str(self.root),
                    "--output",
                    str(output),
                    "--extract-to",
                    str(self.dest),
                    "--quiet",
                    "--strict",
                ]
            )
        self.assertEqual(status, 1)
        self.assertTrue(output.exists())
        self.assertTrue((self.dest / "extraction.json").exists())
