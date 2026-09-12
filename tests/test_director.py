import contextlib
import io
import tempfile
from pathlib import Path
import unittest

from bootdisk_ingest.formats.director import (
    Archive,
    DirectorError,
    UnsupportedDirector,
    Score,
    read_labels,
    read_names,
    read_context,
    read_script,
)
from bootdisk_ingest.formats.director.lingo import decode_instructions
from bootdisk_ingest.formats.director.__main__ import main, observations
from director_fixtures import archive, context, names, put, script, score


class DirectorTests(unittest.TestCase):
    def parse_script(self, code=None):
        a = Archive(
            archive(
                [
                    ("Lnam", names([b"mouseUp", b"launch"])),
                    ("Lscr", script() if code is None else script(code)),
                ]
            )
        )
        return read_script(a, 4, read_names(a, 3))

    def test_container_endianness_does_not_change_payload_endianness(self):
        for endian in ["<", ">"]:
            a = Archive(archive([("Lnam", names([b"alpha", b"beta"]))], endian))
            self.assertEqual(read_names(a, 3), (b"alpha", b"beta"))

    def test_unknown_resource_remains_available(self):
        a = Archive(archive([("ZZZZ", b"\xff\x00historic")]))
        self.assertEqual(a.payload(3), b"\xff\x00historic")

    def test_truncation_and_declared_length_are_rejected(self):
        original = archive([("Lnam", names([b"hello"]))])
        for cutoff in [0, 3, 12, 31, len(original) - 1]:
            with self.subTest(cutoff=cutoff), self.assertRaises(DirectorError):
                Archive(original[:cutoff])

    def test_unknown_version_rejected(self):
        b = bytearray(archive([]))
        put(b, 28, "I", 0x500, "<")
        with self.assertRaises(UnsupportedDirector):
            Archive(b)

    def test_map_count_and_payload_bounds(self):
        for offset, value in [(60, 0xFFFFFFFF), (76 + 3 * 20 + 8, 0xFFFFFFF0)]:
            b = bytearray(archive([("ZZZZ", b"hello")]))
            put(b, offset, "I", value, "<")
            with self.assertRaises(DirectorError):
                Archive(b)

    def test_free_slot_is_not_payload(self):
        a = Archive(archive([("free", b"")]))
        with self.assertRaises(DirectorError):
            a.payload(3)

    def test_wrong_tag_and_missing_reference(self):
        a = Archive(archive([("ZZZZ", b"")]))
        for rid, kind in [(3, "CASt"), (999, None), (-1, None)]:
            with self.assertRaises(DirectorError):
                a.payload(rid, kind)

    def test_truncated_pascal_name(self):
        b = bytearray(names([b"hello"]))
        b[20] = 255
        a = Archive(archive([("Lnam", b)]))
        with self.assertRaises(DirectorError):
            read_names(a, 3)

    def test_context_free_list_preserves_unused_nonempty_script(self):
        a = Archive(
            archive(
                [
                    ("Lnam", names([b"mouseUp", b"launch"])),
                    ("Lscr", script()),
                    ("Lctx", context([(4, -1), (4, -1)], first_unused=1)),
                ]
            )
        )
        c = read_context(a, 5)
        self.assertFalse(c.entries[0].unused)
        self.assertTrue(c.entries[1].unused)
        self.assertEqual(c.entries[1].index, 2)
        self.assertEqual(c.entries[1].resource_id, 4)

    def test_cyclic_and_out_of_range_free_list(self):
        for nxt in [0, 77]:
            a = Archive(
                archive([("Lnam", names([])), ("Lctx", context([(-1, nxt)], first_unused=0))])
            )
            with self.assertRaises(DirectorError):
                read_context(a, 4)

    def test_literal_call_has_actual_pushed_argument(self):
        s = self.parse_script()
        call = s.literal_calls()[0]
        self.assertEqual(
            (call.handler, call.name, call.arguments),
            (b"mouseUp", b"launch", (b"tools\\setup.exe",)),
        )
        self.assertEqual(call.offset, 96)

    def test_unused_literal_is_not_a_call(self):
        self.assertEqual(self.parse_script(b"\x01").literal_calls(), ())

    def test_computed_argument_is_not_guessed(self):
        self.assertEqual(self.parse_script(b"\x49\x00\x42\x01\x57\x01\x01").literal_calls(), ())

    def test_branch_into_argument_sequence_is_not_claimed(self):
        # Branch lands on the second push, so the first argument isn't guaranteed.
        code = b"\x53\x04\x44\x00\x03\x42\x02\x57\x01\x01"
        self.assertEqual(self.parse_script(code).literal_calls(), ())

    def test_bad_constant_name_and_jump_references(self):
        for code in [b"\x44\x01\x01", b"\x44\x08\x01", b"\x57\xff\x01", b"\x53\x01\x01"]:
            with self.subTest(code=code), self.assertRaises(DirectorError):
                self.parse_script(code)

    def test_truncated_operands(self):
        for code in [b"\x44", b"\x84\x00", b"\xc4\x00\x00\x00"]:
            with self.assertRaises(DirectorError):
                decode_instructions(code)

    def test_unknown_opcode_preserved_and_not_interpreted(self):
        self.assertEqual(decode_instructions(b"\x3f")[0].opcode, 0x3F)
        self.assertEqual(self.parse_script(b"\x3f\x42\x01\x57\x01\x01").literal_calls(), ())

    def test_constant_store_pointer_checked(self):
        b = bytearray(script())
        put(b, 88, "I", 0xFFFFFFF0)
        a = Archive(archive([("Lscr", b)]))
        with self.assertRaises(DirectorError):
            read_script(a, 3, (b"mouseUp", b"launch"))

    def test_score_inherits_deltas_and_keeps_snapshot_immutable(self):
        a = Archive(archive([("VWSC", score())]))
        frames = list(Score(a, 3).frames())
        self.assertEqual(len(frames), 2)
        self.assertEqual(
            (frames[0].sprites[0].cast_member, frames[1].sprites[0].cast_member), (77, 78)
        )
        self.assertEqual(frames[1].sprites[0].cast_library, 3)
        self.assertEqual(len(frames[0].main_channels), 144)

    def test_score_invalid_delta(self):
        a = Archive(archive([("VWSC", score([[(4000, b"bad")]]))]))
        with self.assertRaises(DirectorError):
            list(Score(a, 3).frames())

    def test_score_truncated_frame_rejected(self):
        b = bytearray(score())
        put(b, 52, "H", 0xFFFF)
        a = Archive(archive([("VWSC", b)]))
        with self.assertRaises(DirectorError):
            list(Score(a, 3).frames())

    def test_label_duplicates_preserved(self):
        import struct

        b = struct.pack(">HHHHHHH", 2, 1, 0, 1, 3, 2, 6) + b"oneTWO"
        a = Archive(archive([("VWLB", b)]))
        labels = read_labels(a, 3)
        self.assertEqual([(x.frame, x.name) for x in labels], [(1, b"one"), (1, b"TWO")])

    def test_bad_label_offsets_rejected(self):
        import struct

        a = Archive(archive([("VWLB", struct.pack(">HHHHH", 1, 1, 2, 2, 1) + b"ab")]))
        with self.assertRaises(DirectorError):
            read_labels(a, 3)

    def test_cli_error_is_clear_and_does_not_emit_partial_json(self):
        with tempfile.TemporaryDirectory() as root:
            p = Path(root) / "bad.cxt"
            p.write_bytes(b"bad")
            out, err = io.StringIO(), io.StringIO()
            with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
                status = main([str(p)])
            self.assertEqual(status, 2)
            self.assertEqual(out.getvalue(), "")
            self.assertIn("director-reader:", err.getvalue())

    def test_json_byte_view_is_reversible(self):
        a = Archive(
            archive(
                [
                    ("Lnam", names([b"mouseUp", b"launch"])),
                    ("Lscr", script(literal=b"\xff\\x")),
                    ("Lctx", context([(4, -1)])),
                ]
            )
        )
        result = observations(a)
        raw = result["scripts"][0]["literal_calls"][0]["arguments"][0]
        self.assertEqual(bytes.fromhex(raw["hex"]), b"\xff\\x")


class DirectorLinkTests(unittest.TestCase):
    def test_nonstandard_member_start_and_logical_parent(self):
        from director_fixtures import linked_archive
        from bootdisk_ingest.formats.director.links import CastLinks

        links = CastLinks(Archive(linked_archive(parent=76543)))
        self.assertEqual(links.members[1, 10].texts, ((7, b"Generic title"),))
        self.assertNotIn((1, 1), links.members)

    def test_external_path_is_not_opened(self):
        from director_fixtures import linked_archive
        from bootdisk_ingest.formats.director.links import CastLinks

        links = CastLinks(Archive(linked_archive(path=b"/does/not/exist.cxt")))
        self.assertEqual(links.members, {})
        self.assertEqual(links.unresolved_libraries, (1,))

    def test_unknown_binding_is_rejected(self):
        from director_fixtures import linked_archive
        from bootdisk_ingest.formats.director.links import CastLinks

        a = Archive(linked_archive())
        with self.assertRaises(DirectorError):
            CastLinks(a, {99: a})

    def test_invalid_cast_reference_is_rejected(self):
        from director_fixtures import linked_archive

        a = Archive(linked_archive())
        r = a.resource(4)
        b = bytearray(a.data)
        put(b, r.offset + 8, "I", 7)
        with self.assertRaises(DirectorError):
            Archive(b).members(4)

    def test_invalid_library_field_offsets_are_rejected(self):
        from director_fixtures import linked_archive

        a = Archive(linked_archive())
        r = a.resource(3)
        b = bytearray(a.data)
        put(b, r.offset + 8 + 18, "I", 0xFFFFFFFF)
        with self.assertRaises(DirectorError):
            Archive(b).libraries()
