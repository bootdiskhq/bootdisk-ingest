import hashlib
import json
import os
from pathlib import Path
import io
from contextlib import redirect_stderr
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import patch
from bootdisk_ingest.pipeline import ingest_kcd
from bootdisk_ingest.output import write_manifest


class PipelineTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.home = Path(self.temp.name)
        self.root = self.home / "source"
        self.root.mkdir()
        (self.root / "K.DTX").write_bytes(b"[K1]\nTitel=Example\nFolder=App\nSetup=setup.exe\n")
        (self.root / "App").mkdir()
        (self.root / "App/setup.exe").write_bytes(b"executable observation, never run")
        (self.root / "unreferenced.dat").write_bytes(b"also preserved")
        self.output = self.home / "result.json"

    def cli(self, *args):
        from bootdisk_ingest.cli import main
        stderr = io.StringIO()
        with patch.dict(os.environ, {"SOURCE_DATE_EPOCH": "946684800"}), redirect_stderr(stderr):
            code = main([str(self.root), "--output", str(self.output), "--quiet", *args])
        return SimpleNamespace(returncode=code, stderr=stderr.getvalue())

    def test_pipeline_statistics_validation_and_reproducibility(self):
        a = ingest_kcd(self.root, generated_at="2000-01-01T00:00:00+00:00")
        b = ingest_kcd(self.root, generated_at="2000-01-01T00:00:00+00:00")
        self.assertEqual(a, b)
        self.assertTrue(a["validation"]["valid"])
        self.assertEqual(a["generator"]["version"], "1.0.0rc1")
        self.assertEqual(a["schema_version"], "0.9")
        self.assertEqual(a["statistics"]["disc_inventory"]["physical_files"], 3)
        self.assertEqual(a["statistics"]["entry_inventory"]["file_references"], 1)
        self.assertEqual(a["media"], {"available": False})
        self.assertEqual(len(a["validation"]["missing_discovered_assets"]), 3)
        self.assertNotIn(str(self.root), json.dumps(a))

    def test_cli_writes_and_requires_force(self):
        first = self.cli()
        self.assertEqual(first.returncode, 0, first.stderr)
        before = self.output.read_bytes()
        self.assertEqual(self.cli().returncode, 2)
        self.assertEqual(self.output.read_bytes(), before)
        forced = self.cli("--force")
        self.assertEqual(forced.returncode, 0, forced.stderr)
        self.assertEqual(self.output.read_bytes(), before)

    def test_screenshot_bmp_fallback_preserves_observed_case_and_bytes(self):
        image = self.root / "App/SHOT.BMP"
        image.write_bytes(b"source bitmap")
        result = ingest_kcd(self.root)
        observed = result["entries"][0]["files"]["discovered"]["screenshot"]
        self.assertTrue(observed["exists"])
        self.assertEqual(observed["path"], "App/Shot.bmp")
        self.assertEqual(observed["resolved_path"], "App/SHOT.BMP")
        self.assertEqual(observed["sha256"], hashlib.sha256(image.read_bytes()).hexdigest())

    def test_screenshot_jpg_remains_preferred_when_both_exist(self):
        (self.root / "App/Shot.jpg").write_bytes(b"original preferred image")
        (self.root / "App/Shot.bmp").write_bytes(b"alternative image")
        result = ingest_kcd(self.root)
        self.assertEqual(result["entries"][0]["files"]["discovered"]["screenshot"]["path"], "App/Shot.jpg")

    def test_strict_reports_missing_reference_after_writing(self):
        (self.root / "App/setup.exe").unlink()
        result = self.cli("--strict")
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertFalse(json.loads(self.output.read_text())["validation"]["valid"])

    def test_cli_cannot_write_inside_source(self):
        self.output = self.root / "manifest.json"
        self.assertEqual(self.cli().returncode, 2)
        self.assertFalse(self.output.exists())

    def test_cli_cannot_replace_image(self):
        self.output.write_bytes(b"original image")
        self.assertEqual(self.cli("--image", str(self.output), "--force").returncode, 2)
        self.assertEqual(self.output.read_bytes(), b"original image")

    def test_explicit_missing_image_is_error(self):
        with self.assertRaises(ValueError):
            ingest_kcd(self.root, image=self.home / "missing.iso")

    def test_image_hash_is_independent(self):
        image = self.home / "source.iso"
        image.write_bytes(b"image bytes")
        m = ingest_kcd(self.root, image=image)
        self.assertEqual(m["media"]["sha256"], hashlib.sha256(b"image bytes").hexdigest())
        self.assertFalse(m["disc"]["filesystem"]["iso9660"])

    def test_atomic_failure_keeps_previous_output(self):
        self.output.write_text("previous")
        with patch("os.replace", side_effect=OSError("simulated publication failure")):
            with self.assertRaises(OSError):
                write_manifest({"new": True}, self.output, overwrite=True)
        self.assertEqual(self.output.read_text(), "previous")
        self.assertEqual(sorted(x.name for x in self.home.iterdir()), ["result.json", "source"])

    def test_relocation_does_not_change_manifest(self):
        import shutil
        other = self.home / "relocated"
        shutil.copytree(self.root, other)
        self.assertEqual(ingest_kcd(self.root, generated_at="fixed"), ingest_kcd(other, generated_at="fixed"))

    def test_malformed_source_produces_no_output(self):
        (self.root / "K.DTX").write_bytes(b"broken")
        self.assertEqual(self.cli().returncode, 2)
        self.assertFalse(self.output.exists())

    def test_legacy_report_executes(self):
        from bootdisk_ingest.output import print_report
        from contextlib import redirect_stdout
        report = io.StringIO()
        with redirect_stdout(report):
            print_report(ingest_kcd(self.root), self.output)
        self.assertIn("1.0.0rc1", report.getvalue())
