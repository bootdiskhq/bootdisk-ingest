import base64
import tempfile
import unittest
from pathlib import Path
from bootdisk_ingest.pipeline import ingest_kcd


class VariantTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
        (self.root/'K.DTX').write_text('[K1]\nTitel=Example\nFolder=Tools/App\n')
        (self.root/'Tools/App').mkdir(parents=True)

    def test_unindented_prose_preserves_duplicates_and_exact_source(self):
        data=b'[I1]\nNavn=Example\nFolder=Tools/App\nInstruksNo=First line\nRepeated\nRepeated\nSetup=setup.exe\n'
        (self.root/'Tools.dtx').write_bytes(data)
        m=ingest_kcd(self.root);entry=m['entries'][1]
        self.assertEqual(entry['raw']['InstruksNo'],'First line\nRepeated\nRepeated')
        self.assertEqual(entry['normalized']['installer'],'Tools/App/setup.exe')
        doc=m['source']['supplemental_metadata'][0]
        self.assertEqual(base64.b64decode(doc['raw_base64']),data)
        self.assertEqual(doc['text_projection']['continuation_lines'],[5,6])

    def test_malformed_non_prose_still_fails(self):
        import configparser
        (self.root/'Tools.dtx').write_bytes(b'[I1]\nNavn=Example\nFolder=Tools/App\naccidental garbage\n')
        with self.assertRaises(configparser.Error):ingest_kcd(self.root)

    def test_lessons_preserved_separately_without_new_programs(self):
        raw=b'[Intro]\nIntroTitel=Learn\n[L1]\nTekst1=First\nSecond\n'
        (self.root/'Tools/App/DataNo.dtx').write_bytes(raw)
        m=ingest_kcd(self.root);self.assertEqual(len(m['entries']),1)
        doc=m['source']['supplemental_metadata'][0]
        self.assertEqual(doc['role'],'workshop_lesson_document')
        self.assertEqual(doc['associated_entry_ids'],['K1'])
        self.assertEqual(doc['publication_status'],'preserved_only')
        self.assertEqual(doc['sections']['L1']['Tekst1'],'First\nSecond')
        self.assertEqual(base64.b64decode(doc['raw_base64']),raw)
        self.assertEqual(m['source']['coverage']['unprocessed_metadata'],[])
        self.assertFalse(m['source']['coverage']['complete_disc'])

    def test_lesson_filename_does_not_hide_unknown_menu_or_section(self):
        path=self.root/'Tools/App/DataNo.dtx'
        path.write_text('[K2]\nTitel=Unseen program\n')
        m=ingest_kcd(self.root)
        self.assertEqual(m['source']['coverage']['unprocessed_metadata'],['Tools/App/DataNo.dtx'])
        path.write_text('[L1]\nTekst1=Known\n[K2]\nTitel=Unseen program\n')
        m=ingest_kcd(self.root)
        self.assertEqual(m['source']['coverage']['metadata_files'][-1]['unprojected_sections'],['K2'])
