import base64
import configparser
import tempfile
import unittest
from pathlib import Path
from bootdisk_ingest.inventory import build_inventory
from bootdisk_ingest.adapters.kcd.parser import parse_disc


class ParserTests(unittest.TestCase):
    def parse(self, raw, files=None, metadata_name="K.DTX"):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / metadata_name).write_bytes(raw)
            for name, data in (files or {}).items():
                path = root / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(data)
            return parse_disc(root, build_inventory(root), generated_at="2000-01-01T00:00:00+00:00")

    def test_real_bytes_raw_normalized_and_references(self):
        raw = b"[Generelt]\r\nName=Disc\r\n[K1]\r\nTitel=Bl\xe5\r\nFolder=Tools\\Foo\r\nSetup=SETUP.EXE\r\nCPU=42\r\nMystery=ja\r\n"
        m = self.parse(raw, {"Tools/Foo/setup.exe": b"payload"})
        entry = m["entries"][0]
        self.assertEqual(entry["raw"]["Titel"], "Blå")
        self.assertEqual(entry["raw"]["Folder"], "Tools\\Foo")
        self.assertEqual(entry["normalized"]["folder"], "Tools/Foo")
        self.assertEqual(entry["normalized"]["categories"], ["Mystery"])
        self.assertIsNone(entry["normalized"]["requirements"]["cpu"]["mhz"])
        self.assertEqual(entry["interpretations"]["CPU"]["confidence"], "interpreted")
        self.assertEqual(entry["files"]["referenced"]["installer"]["resolved_path"], "Tools/Foo/setup.exe")
        self.assertEqual(entry["content_identity"]["file_count"], 1)
        self.assertEqual(base64.b64decode(m["source"]["dtx_file"]["raw_base64"]), raw)

    def test_duplicate_unknown_and_undefined_bytes_are_preserved(self):
        raw = b";comment\n[Unknown]\nX=\x81\n[K1]\nTitel=First\nTitel=Last\n"
        m = self.parse(raw)
        self.assertEqual(base64.b64decode(m["source"]["dtx_file"]["raw_base64"]), raw)
        self.assertEqual(m["entries"][0]["raw"]["Titel"], "Last")
        self.assertIn("Unknown", m["source"]["sections"])
        self.assertEqual(len(m["source"]["parser_warnings"]), 3)
        self.assertTrue(any("Undefined CP1252" in w for w in m["source"]["parser_warnings"]))
        self.assertTrue(any("Duplicate INI" in w for w in m["source"]["parser_warnings"]))
        self.assertIn("K.DTX: unprojected section Unknown", m["source"]["parser_warnings"])

    def test_lowercase_metadata_resolution(self):
        m = self.parse(b"[Generelt]\nX=y\n", metadata_name="k.dtx")
        self.assertEqual(m["source"]["dtx_file"]["resolved_path"], "k.dtx")

    def test_malformed_metadata_fails(self):
        with self.assertRaises(configparser.Error):
            self.parse(b"not an ini file")

    def test_changed_metadata_fails(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / "K.DTX").write_bytes(b"[K1]\nTitel=Before")
            inventory = build_inventory(root)
            (root / "K.DTX").write_bytes(b"[K1]\nTitel=After")
            with self.assertRaisesRegex(ValueError, "changed"):
                parse_disc(root, inventory)


class LocalizedTitleTests(unittest.TestCase):
    parse = ParserTests.parse
    def test_norwegian_title_over_common_and_other_languages(self):
        m = self.parse(b"[K1]\nTitel=Common\nTitelDK=Dansk\nTitelNO=Norsk\nGlobalNO=Omtale\n")
        self.assertEqual(m['entries'][0]['normalized']['title'], 'Norsk')
        self.assertEqual(m['entries'][0]['raw']['Titel'], 'Common')
        self.assertEqual(m['source']['sections']['K1']['TitelNO'], 'Norsk')

    def test_field_case_and_no_foreign_language_fallback(self):
        for field in ('TitelNo', 'TitelNO', 'titelno'):
            self.assertEqual(self.parse(('[K1]\n'+field+'=Norsk\n').encode())['entries'][0]['normalized']['title'], 'Norsk')
        self.assertIsNone(self.parse(b'[K1]\nTitelDK=Dansk\n')['entries'][0]['normalized']['title'])

    def test_conflicting_norwegian_fields_fail(self):
        with self.assertRaisesRegex(ValueError, 'Conflicting'):
            self.parse(b'[K1]\nTitelNO=One\nTitelNo=Other\n')
