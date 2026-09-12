"""Qualify a second original D6 source without changing the binary reader."""

import hashlib
import os
from pathlib import Path
import unittest

from bootdisk_ingest.formats.director import (
    Archive,
    Score,
    read_context,
    read_names,
    read_script,
    read_labels,
)
from bootdisk_ingest.formats.director.links import CastLinks


@unittest.skipUnless(
    os.environ.get("BOOTDISK_DIRECTOR_KCD4_FIXTURES"),
    "Original K-CD 4/2000 fixtures not configured",
)
class DirectorKcd4MediaTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        root = Path(os.environ["BOOTDISK_DIRECTOR_KCD4_FIXTURES"])
        cls.movie = Archive.open(root / "K-CN.dxr")
        cls.cast = Archive.open(root / "Constant.cxt")
        for a, digest in [
            (cls.movie, "0ad0224bfeb9111bdd25e402a2feee8340ee8f84ba361e703a5d19ef111fe6e0"),
            (cls.cast, "75f4595a062dc351bbc2ef57152202ed35fa3c9e16b8fbb32528e48afc193c56"),
        ]:
            if hashlib.sha256(a.data).hexdigest() != digest:
                raise ValueError("Fixture hash differs from qualified K-CD 4/2000 bytes")
        cls.links = CastLinks(cls.movie, {3: cls.cast})
        cls.frames = list(Score(cls.movie, cls.movie.ids("VWSC")[0]).frames())

    def targets(self, frame, library, member):
        sprite = next(
            s
            for s in self.frames[frame - 1].sprites
            if s.kind and (s.cast_library, s.cast_member) == (library, member)
        )
        link = self.links.resolve(sprite)
        self.assertIsNotNone(link)
        self.assertIsNotNone(link.script)
        self.assertFalse(link.script_unused)
        return [c.arguments[0] for c in link.script.literal_calls() if c.name == b"baRunProgram"]

    def test_different_resource_and_score_counts(self):
        self.assertEqual(len(self.movie.members(self.movie.ids("CAS*")[0])), 121)
        self.assertEqual(sum(len(self.movie.members(i)) for i in self.movie.ids("CAS*")), 314)
        self.assertEqual(len(self.cast.resources), 2462)
        self.assertEqual(len(self.cast.members(self.cast.ids("CAS*")[0])), 440)
        self.assertEqual(self.cast.standalone_bounds(), (1, 451))
        self.assertEqual(len(self.frames), 1196)
        self.assertEqual(len(read_labels(self.movie, self.movie.ids("VWLB")[0])), 651)
        self.assertEqual(self.links.unresolved_libraries, (4, 5, 6))

    def test_all_scripts_decode_without_profile_changes(self):
        for archive, expected in [(self.movie, 94), (self.cast, 218)]:
            count = 0
            for rid in archive.ids("Lctx"):
                context = read_context(archive, rid)
                names = read_names(archive, context.names_id)
                for entry in context.entries:
                    if entry.resource_id != -1:
                        read_script(archive, entry.resource_id, names)
                        count += 1
            self.assertEqual(count, expected)

    def test_three_game_targets_have_changed(self):
        for direct, library, member, warning, setup, target in [
            (260, 3, 43, 264, 385, b"Dink\\Setup.exe"),
            (269, 2, 89, 273, 386, b"Raising\\Setup.exe"),
            (278, 3, 42, 282, 387, b"Cult\\Setup.exe"),
        ]:
            with self.subTest(target=target):
                self.assertEqual(self.targets(direct, library, member), [target])
                self.assertEqual(self.targets(warning, 3, setup), [target])

    def test_geometra_uses_embedded_cast_and_empty_shared_slots(self):
        self.assertEqual(self.targets(331, 1, 121), [b"Geometra\\Setup.exe"])
        self.assertEqual(self.targets(334, 1, 122), [b"Geometra\\Setup.exe"])
        self.assertNotIn((3, 168), self.links.members)
        self.assertNotIn((3, 411), self.links.members)

    def test_word_language_variant_follows_score_not_member_name(self):
        self.assertEqual(self.targets(403, 2, 118), [b"Word\\WordsampleNo.exe"])
        self.assertEqual(self.targets(406, 1, 27), [b"Word\\WordSampleNo.exe"])
        shared = self.links.members[3, 420]
        internal = self.links.members[1, 27]
        self.assertEqual(shared.cast.name, internal.cast.name)
        self.assertEqual(
            [c.arguments[0] for c in shared.script.literal_calls() if c.name == b"baRunProgram"],
            [b"Word\\WordSampleSv.exe"],
        )

    def test_norwegian_year_index_is_explicit(self):
        self.assertEqual(self.targets(419, 2, 191), [b"Index\\Norsk\\Setup.exe"])
        self.assertEqual(self.targets(422, 2, 192), [b"Index\\Norsk\\Setup.exe"])

    def test_missing_albert_warning_member_remains_unresolved(self):
        self.assertEqual(self.targets(355, 1, 97), [b"AabergNo\\Setup.exe"])
        sprite = next(s for s in self.frames[356].sprites if s.channel == 91)
        self.assertEqual((sprite.kind, sprite.cast_library, sprite.cast_member), (16, 3, 414))
        self.assertIsNone(self.links.resolve(sprite))

    def test_inherited_nhl_references_do_not_override_current_photoline(self):
        self.assertEqual(self.targets(430, 3, 428), [b"PhotoLine\\Setup.exe"])
        self.assertEqual(self.targets(431, 3, 441), [b"PhotoLine\\Setup.exe"])
        stale = self.links.members[3, 430]
        self.assertEqual(
            [c.arguments[0] for c in stale.script.literal_calls() if c.name == b"baRunProgram"],
            [b"NHL 2000\\NHL2000Demo.exe"],
        )

    def test_dxball_shell_arguments_stay_separate(self):
        link = self.links.members[2, 98]
        self.assertEqual(
            [c.arguments for c in link.script.literal_calls() if c.name == b"baShell"],
            [(b"open", b"dxb2game.exe", b"", b"DXBall", b"Normal")],
        )
        self.assertEqual(self.targets(385, 3, 417), [b"DXBall\\DXB2game.exe"])

    def test_new_monthly_text_and_external_paths_remain_raw(self):
        raw = [
            text
            for link in self.links.members.values()
            if link.library == 2
            for _, text in link.texts
        ]
        self.assertIn(b"Dink Smallwood", raw)
        self.assertIn(b"Geometra", raw)
        self.assertEqual(self.movie.libraries()[2].path, b"G:\\DSource\\Constant.cxt")
