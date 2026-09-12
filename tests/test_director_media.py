"""Opt-in original-byte regressions; set BOOTDISK_DIRECTOR_FIXTURES to the two files."""

import hashlib
import os
from pathlib import Path
import unittest
from bootdisk_ingest.formats.director import (
    Archive,
    DirectorError,
    Score,
    read_context,
    read_names,
    read_script,
    read_labels,
)
from bootdisk_ingest.formats.director.links import CastLinks
from director_fixtures import put


@unittest.skipUnless(
    os.environ.get("BOOTDISK_DIRECTOR_FIXTURES"), "Original Director fixtures not configured"
)
class DirectorMediaTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        root = Path(os.environ["BOOTDISK_DIRECTOR_FIXTURES"])
        cls.movie = Archive.open(root / "K-CN.dxr")
        cls.cast = Archive.open(root / "Constant.cxt")
        for a, digest in [
            (cls.movie, "ae4a51fc45f97c1f6a7195e13cee8c1287849d6ac6d326a61c1710789e14f82c"),
            (cls.cast, "ca69e7af983bbeb1bd87a954ea25a90f12458148d0f373cfc0876f7f09f121c5"),
        ]:
            if hashlib.sha256(a.data).hexdigest() != digest:
                raise ValueError("Director fixture hash differs from qualified K-CD 1/2000 bytes")
        cls.links = CastLinks(cls.movie, {3: cls.cast})
        cls.frames = list(Score(cls.movie, cls.movie.ids("VWSC")[0]).frames())

    def targets(self, frame, member):
        sprite = next(
            s
            for s in self.frames[frame - 1].sprites
            if (s.cast_library, s.cast_member) == (3, member) and s.kind
        )
        link = self.links.resolve(sprite)
        self.assertFalse(link.script_unused)
        return [c.arguments[0] for c in link.script.literal_calls() if c.name == b"baRunProgram"]

    def test_structural_counts(self):
        self.assertEqual(len(self.cast.resources), 2271)
        self.assertEqual(len(self.cast.members(self.cast.ids("CAS*")[0])), 446)
        self.assertEqual(len(read_context(self.cast, 1344).entries), 229)
        self.assertEqual(len(self.frames), 1163)
        self.assertEqual(len(read_labels(self.movie, 11)), 624)
        self.assertEqual(self.links.unresolved_libraries, (4, 5, 6))

    def test_every_registered_script_is_decoded(self):
        for archive, expected in [(self.cast, 229), (self.movie, 88)]:
            count = 0
            for rid in archive.ids("Lctx"):
                context = read_context(archive, rid)
                names = read_names(archive, context.names_id)
                for entry in context.entries:
                    if entry.resource_id != -1:
                        read_script(archive, entry.resource_id, names)
                        count += 1
            self.assertEqual(count, expected)

    def test_four_launch_chains_keep_original_bytes(self):
        rows = [
            (356, 170, 357, 413, b"WinAmp\\winamp25e_full.exe"),
            (362, 336, 364, 414, b"Half-Life\\HLUplink.exe"),
            (267, 43, 271, 385, b"Prince3D\\Setup.exe"),
            (285, 42, 289, 387, b"Unreal\\Setup.exe"),
        ]
        for direct, member, warning, setup, target in rows:
            with self.subTest(target=target):
                self.assertEqual(self.targets(direct, member), [target])
                self.assertEqual(self.targets(warning, setup), [target])

    def test_four_conflicts_remain_conflicts(self):
        rows = [
            (437, 428, 438, 441, b"Zing Netscape\\ZingNet.exe"),
            (450, 430, 452, 443, b"Excel\\Sample.exe"),
            (457, 431, 459, 444, b"Word\\WordSample.exe"),
            (470, 432, 472, 445, b"Excel\\XLViewer.exe"),
        ]
        for direct, member, warning, setup, target in rows:
            with self.subTest(frame=direct):
                self.assertEqual(self.targets(direct, member), [b"NHL 2000\\NHL2000Demo.exe"])
                self.assertEqual(self.targets(warning, setup), [target])

    def test_warning_navigation_is_a_go_call(self):
        link = self.links.members[3, 170]
        self.assertEqual(
            [c.arguments for c in link.script.literal_calls() if c.name == b"go"], [(b"K3Chicken",)]
        )
        self.assertEqual(link.cast.name, b"KProg3Install")

    def test_missing_external_cast_stays_unresolved(self):
        links = CastLinks(self.movie)
        self.assertEqual(links.unresolved_libraries, (3, 4, 5, 6))
        sprite = next(
            s for s in self.frames[355].sprites if s.cast_library == 3 and s.cast_member == 170
        )
        self.assertIsNone(links.resolve(sprite))

    def test_monthly_title_is_linked_by_resource(self):
        raw = [
            text
            for link in self.links.members.values()
            if link.library == 2
            for _, text in link.texts
        ]
        self.assertIn(b"WinAmp 2.50e\r\r", raw)
        self.assertIn(b"Prince of Persia 3D", raw)

    def test_external_cast_bounds_must_match(self):
        b = bytearray(self.cast.data)
        r = self.cast.resource(self.cast.ids("DRCF")[0])
        put(b, r.offset + 8 + 12, "H", 2)
        with self.assertRaises(DirectorError):
            CastLinks(self.movie, {3: Archive(b)})

    def test_corrupt_cast_info_and_script_links_fail(self):
        member = self.links.members[3, 170].cast
        r = self.cast.resource(member.resource_id)
        for relative, value in [(12, 0xFFFFFFFF), (28, 0x7FFFFFFF)]:
            b = bytearray(self.cast.data)
            put(b, r.offset + 8 + relative, "I", value)
            with self.subTest(relative=relative), self.assertRaises(DirectorError):
                CastLinks(self.movie, {3: Archive(b)})

    def test_historical_external_paths_are_only_data(self):
        libraries = self.movie.libraries()
        self.assertEqual(libraries[2].name, b"Constant")
        self.assertTrue(libraries[2].path.startswith(b"E:"))
        self.assertEqual(libraries[1].resource_id, 1033)
