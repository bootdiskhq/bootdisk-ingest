"""Public adapter policy and synthetic navigation; original media are optional."""

from contextlib import redirect_stderr, redirect_stdout
from dataclasses import replace
import hashlib
import io
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace as NS
import unittest
from unittest.mock import patch

from bootdisk_ingest.adapters.kcd.director import (
    MenuProjection,
    calls,
    launch_path,
    parse_director_disc,
    relative_target,
    validate_director,
)
from bootdisk_ingest.cli import main
from bootdisk_ingest.formats.director import DirectorError
from bootdisk_ingest.formats.director.lingo import LiteralCall
from bootdisk_ingest.pipeline import ingest_kcd


def call(name, args):
    return LiteralCall(b"mouseUp", 100, name, tuple(args))


def source_inventory(root):
    files = []
    for name in ("K-CN.dxr", "Constant.cxt"):
        data = (root / name).read_bytes()
        files.append(dict(path=name, size=len(data), sha256=hashlib.sha256(data).hexdigest()))
    return {"files": files}


class AdapterPolicyTests(unittest.TestCase):
    def test_shell_working_directory_is_part_of_target(self):
        self.assertEqual(
            launch_path(call(b"baShell", [b"open", b"dxb2game.exe", b"", b"DXBall", b"Normal"])),
            "DXBall/dxb2game.exe",
        )

    def test_spaces_and_original_case_survive(self):
        self.assertEqual(
            launch_path(call(b"baRunProgram", [b"Zing Netscape\\ZingNet.exe", b"Normal", 0])),
            "Zing Netscape/ZingNet.exe",
        )

    def test_unsafe_and_computed_paths_are_not_resolved(self):
        for path in (
            b"C:\\Setup.exe",
            b"\\\\server\\x",
            b"/tmp/x",
            b"../x",
            b"x\\..\\y",
            b"x//y",
            b"x\0y",
            b'"x.exe" /arg',
            b"x:stream",
            42,
            b"\x81.exe",
        ):
            with self.subTest(path=path), self.assertRaises(ValueError):
                relative_target(path)

    def test_shell_arguments_and_unknown_signature_stay_unresolved(self):
        for c in (
            call(b"baShell", [b"open", b"x.exe", b"/install", b"", b"Normal"]),
            call(b"baShell", [b"print", b"x.exe", b"", b"", b"Normal"]),
            call(b"baRunProgram", [b"x.exe"]),
            call(b"other", [b"x.exe"]),
        ):
            with self.subTest(call=c), self.assertRaises(ValueError):
                launch_path(c)

    def test_unused_script_is_not_an_active_call_source(self):
        c = call(b"go", [b"KDisk4Mere"])
        link = NS(script=NS(literal_calls=lambda: (c,)), script_unused=True)
        self.assertEqual(calls(link), ())
        link.script_unused = False
        self.assertEqual(calls(link), (c,))

    def test_page_chain_uses_buttons_and_retains_duplicate_label_evidence(self):
        p = MenuProjection.__new__(MenuProjection)
        frames = [
            NS(number=n, main_channels=bytes([0, 1, 0, 11 if n < 4 else 12])) for n in range(1, 6)
        ]
        p.frames = frames
        p.labels = {b"KDisk1Mere": 1, b"KDisk2Mere": 4}
        p.label_frames = {b"K1D6": [2, 5], b"K2D6": [5]}
        p.ambiguous_labels = set()
        p.navigation = []
        p.action = lambda f: NS(
            script_unused=False,
            script=NS(
                literal_calls=lambda: (
                    replace(
                        call(b"go", [b"K1D6" if f.number < 4 else b"K2D6"]), handler=b"enterFrame"
                    ),
                )
            ),
        )

        def sprites(f):
            target = b"KDisk2Mere" if f.number == 2 else b"KDisk1Mere"
            return [
                (
                    NS(channel=20),
                    NS(
                        script_unused=False,
                        script=NS(literal_calls=lambda: (call(b"go", [target]),)),
                    ),
                )
            ]

        p.sprites = sprites
        p.location = lambda f, s, l: {"frame": f.number}
        self.assertEqual([n for n, f in p.page_chain()], [1, 2])
        self.assertEqual(p.navigation[0]["all_label_frames"], [2, 5])
        self.assertEqual(p.navigation[0]["buttons"][0]["frame"], 2)

    def test_ambiguous_selected_label_fails_closed(self):
        p = MenuProjection.__new__(MenuProjection)
        p.ambiguous_labels = {b"Spil2"}
        with self.assertRaises(DirectorError):
            p.frame(b"Spil2")

    def test_dtx_still_takes_precedence_over_director(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "k.dtx").write_text("[Generelt]\nTitel=Test\n", encoding="cp1252")
            (root / "K-CN.dxr").write_bytes(b"not a Director movie")
            with patch("bootdisk_ingest.pipeline.parse_director_disc") as adapter:
                result = ingest_kcd(root, generated_at="fixed")
            adapter.assert_not_called()
            self.assertEqual(result["schema_version"], "0.9")

    def test_no_dtx_dispatches_and_strict_writes_before_failure(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp) / "source"
            root.mkdir()
            output = Path(tmp) / "manifest.json"
            # Test CLI policy with a minimal adapter result, independently of original media.
            entry = {
                "source_id": "K1D1",
                "raw": {},
                "normalized": {
                    "title": "Test",
                    "categories": [],
                    "requirements": {"cpu": {"interpretation": None}},
                },
                "files": {"referenced": {}, "discovered": {}},
                "content_identity": {"file_count": 0, "total_size": 0},
                "issues": ["unresolved_direct_launch"],
            }
            manifest = {"source": {"format": "kcd-director-d6-v1"}, "disc": {}, "entries": [entry]}
            with (
                patch("bootdisk_ingest.pipeline.parse_director_disc", return_value=manifest),
                redirect_stdout(io.StringIO()),
                redirect_stderr(io.StringIO()),
            ):
                status = main([str(root), "--output", str(output), "--strict"])
            self.assertEqual(status, 1)
            saved = json.loads(output.read_text())
            self.assertFalse(saved["validation"]["valid"])
            self.assertEqual(saved["validation"]["missing_referenced_files"], [])

    def test_malformed_movie_returns_two_and_no_output(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp) / "source"
            root.mkdir()
            (root / "K-CN.dxr").write_bytes(b"broken")
            output = Path(tmp) / "manifest.json"
            with redirect_stderr(io.StringIO()):
                status = main([str(root), "--output", str(output), "--quiet"])
            self.assertEqual(status, 2)
            self.assertFalse(output.exists())

    def test_empty_catalog_is_not_valid(self):
        self.assertFalse(validate_director([])["valid"])


class MediaAssertions:
    def entry(self, source_id):
        return next(e for e in self.result["entries"] if e["source_id"] == source_id)

    def paths(self, source_id, branch):
        return [v["file"]["path"] for v in self.entry(source_id)["evidence"]["launches"][branch]]

    def test_source_changed_after_inventory_is_rejected(self):
        inv = source_inventory(self.root)
        inv["files"][0]["sha256"] = "0" * 64
        with self.assertRaisesRegex(DirectorError, "changed after inventory"):
            parse_director_disc(self.root, inv)

    def test_all_entries_have_traceable_title_and_launch_evidence(self):
        for e in self.result["entries"]:
            self.assertIn("base64", e["evidence"]["selection"]["title"])
            self.assertTrue(e["evidence"]["texts"])
            for values in e["evidence"]["launches"].values():
                for v in values:
                    self.assertGreater(v["script_resource"], 0)
                    self.assertGreater(v["offset"], 0)
                    self.assertGreater(v["frame"], 0)

    def test_deterministic_projection(self):
        again = parse_director_disc(self.root, source_inventory(self.root), generated_at="fixed")
        self.assertEqual(self.result, again)


@unittest.skipUnless(os.environ.get("BOOTDISK_DIRECTOR_FIXTURES"), "K-CD 1/2000 not configured")
class AdapterMedia1Tests(MediaAssertions, unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root = Path(os.environ["BOOTDISK_DIRECTOR_FIXTURES"])
        cls.result = parse_director_disc(cls.root, source_inventory(cls.root), generated_at="fixed")

    def test_twenty_one_candidates_and_four_menu_pages(self):
        self.assertEqual(len(self.result["entries"]), 21)
        self.assertEqual([n["page"] for n in self.result["source"]["navigation"]], [1, 2, 3, 4])
        self.assertNotIn("K4D4", {e["source_id"] for e in self.result["entries"]})

    def test_four_nhl_conflicts_remain_unrepaired(self):
        for source_id in ("K3D2", "K3D4", "K3D5", "K4D1"):
            self.assertIn("conflicting_launch_targets", self.entry(source_id)["issues"])
            self.assertEqual(self.paths(source_id, "direct"), ["NHL 2000/NHL2000Demo.exe"])
            self.assertNotEqual(
                self.paths(source_id, "warning_continue"), self.paths(source_id, "direct")
            )

    def test_focal_program_mappings(self):
        for key, target in [
            ("Spil1", "Prince3D/Setup.exe"),
            ("Spil3", "Unreal/Setup.exe"),
            ("K1D3", "WinAmp/winamp25e_full.exe"),
            ("K1D4", "Half-Life/HLUplink.exe"),
        ]:
            self.assertEqual(self.paths(key, "direct"), [target])
            self.assertEqual(self.paths(key, "warning_continue"), [target])


@unittest.skipUnless(
    os.environ.get("BOOTDISK_DIRECTOR_KCD4_FIXTURES"), "K-CD 4/2000 not configured"
)
class AdapterMedia4Tests(MediaAssertions, unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root = Path(os.environ["BOOTDISK_DIRECTOR_KCD4_FIXTURES"])
        cls.result = parse_director_disc(cls.root, source_inventory(cls.root), generated_at="fixed")

    def test_sixteen_candidates_without_stale_fourth_page(self):
        self.assertEqual(len(self.result["entries"]), 16)
        self.assertEqual([n["page"] for n in self.result["source"]["navigation"]], [1, 2, 3])
        self.assertFalse(any(e["source_id"].startswith("K4") for e in self.result["entries"]))
        self.assertNotIn("K3D4", {e["source_id"] for e in self.result["entries"]})

    def test_missing_links_are_not_filled_from_other_cast_members(self):
        self.assertEqual(self.paths("K1D2", "direct"), [])
        self.assertEqual(self.paths("K1D2", "warning_continue"), ["Geometra/GImages.exe"])
        self.assertEqual(self.paths("K1D4", "warning_continue"), [])
        self.assertIn("unresolved_warning_continue_launch", self.entry("K1D4")["issues"])
        self.assertEqual(self.paths("K2D5", "warning_continue"), ["Word/WordSampleNo.exe"])

    def test_auxiliary_directx_button_is_not_a_conflicting_installer(self):
        e = self.entry("K1D1")
        self.assertEqual(self.paths("K1D1", "direct"), ["Geometra/Setup.exe"])
        self.assertNotIn("conflicting_launch_targets", e["issues"])
        self.assertTrue(
            any(
                v.get("file", {}).get("path") == "DirectX7/DXSetup.exe"
                for v in e["evidence"]["other_launch_controls"]
            )
        )

    def test_cult_text_comes_from_internal_library(self):
        e = self.entry("Spil3")
        self.assertEqual(e["normalized"]["title"], "Cult")
        self.assertEqual(e["evidence"]["selection"]["library"], 1)
        self.assertEqual(e["evidence"]["description_source"]["library"], 1)
        self.assertTrue(e["normalized"]["description"].startswith("I Cult"))
