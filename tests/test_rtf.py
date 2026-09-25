import unittest
from bootdisk_ingest.formats.rtf import plain_text


class RtfTests(unittest.TestCase):
    def test_body_preserves_paragraphs_escapes_and_ignores_metadata(self):
        raw = br"{\rtf1\ansi\ansicpg1252{\fonttbl{\f0\fcharset0 Arial;}}{\info{\title Secret}}{\*\unknown hidden}\f0 Bl\'e5 {\b tekst}\par \{x\} \\ \tab slutt}"
        self.assertEqual(plain_text(raw), "Blå tekst\n{x} \\ \tslutt")

    def test_unicode_fallback_and_scoped_hidden_text(self):
        self.assertEqual(plain_text(br"{\rtf1\ansi\uc1 \u229?{\uc0 \u248} x{\v hidden}\v0 y}"), "åø xy")

    def test_invalid_and_unsupported_sources_fail(self):
        for raw in [b"plain", br"{\rtf1 unfinished", br"{\rtf1\ansicpg932 text}",
                    br"{\rtf1\bin4 abcd}", br"{\rtf1\u999999?}",
                    br"{\rtf1{\fonttbl{\f1\fcharset204 Cyrillic;}}\f1 text}"]:
            with self.subTest(raw=raw), self.assertRaises(ValueError): plain_text(raw)

    def test_terminal_nul_is_not_body_text(self):
        self.assertEqual(plain_text(b"{\\rtf1 Original}\r\n\x00"), "Original")
        with self.assertRaises(ValueError): plain_text(b"{\\rtf1 Original}\x00suffix")
        with self.assertRaises(ValueError): plain_text(b"{\\rtf1 Origi\x00nal}")

    def test_fields_show_result_without_executing_instruction(self):
        raw=br'{\rtf1{\field{\*\fldinst INCLUDETEXT "some-file"}{\fldrslt Original text}}}'
        self.assertEqual(plain_text(raw), 'Original text')
