import base64
import configparser
import hashlib
import io
from contextlib import redirect_stdout
from pathlib import Path
import tempfile
import unittest

from bootdisk_ingest.pipeline import ingest_kcd
from bootdisk_ingest.inventory import build_inventory
from bootdisk_ingest.adapters.kcd.parser import parse_disc
from bootdisk_ingest.output import print_report
from bootdisk_ingest.extraction import extract_entries


class ToolsDtxTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.home=Path(self.temp.name);self.root=self.home/'disc';self.root.mkdir()
        (self.root/'K.DTX').write_bytes(b'[Generelt]\nSprog=Norsk\n[K23]\nTitel=CPU-Z\nFolder=Tools/CPUZ\nSetup=Setup.exe\nGlobal=Original K description\n')
        for folder in ['CPUZ','AdAware']:
            d=self.root/'Tools'/folder;d.mkdir(parents=True)
            (d/'Setup.exe').write_bytes(b'never execute');(d/'Shot.jpg').write_bytes(b'image')
        self.tools=self.root/'TOOLS.DTX'
        self.raw=('[I1]\r\nNavn=Ad-aware\r\nFolder=Tools\\AdAware\r\nSetup=setup.EXE\r\n'
                  'InstruksNo=Norsk omtale æøå.\r\nInstruksDK=Dansk tekst\r\nSpil=Ja\r\nKategori1=3\r\n'
                  '[I2]\r\nNavn=Cpu-Z\r\nFolder=Tools\\cpuz\r\nSetup=Setup.exe\r\nInstruksNo=Verktøyomtale\r\n').encode('cp1252')

    def run_disc(self):return ingest_kcd(self.root,generated_at='2001-01-01T00:00:00+00:00')

    def test_adds_tools_without_changing_primary_entries_or_deduplicating(self):
        before=self.run_disc();self.tools.write_bytes(self.raw);after=self.run_disc()
        self.assertEqual(after['entries'][:1],before['entries'])
        self.assertEqual([e['source_id'] for e in after['entries']],['K23','I1','I2'])
        e=after['entries'][1]
        self.assertEqual(e['raw']['Navn'],'Ad-aware');self.assertNotIn('Titel',e['raw']);self.assertNotIn('Global',e['raw'])
        self.assertEqual(e['normalized']['title'],'Ad-aware')
        self.assertEqual(e['normalized']['description'],'Norsk omtale æøå.')
        self.assertEqual(e['normalized']['categories'],[])
        self.assertEqual(e['raw']['Spil'],'Ja')
        self.assertEqual(e['evidence']['description_tools']['text'],'Norsk omtale æøå.')
        self.assertTrue(e['files']['discovered']['screenshot']['exists'])
        self.assertEqual(e['files']['referenced']['installer']['resolved_path'],'Tools/AdAware/Setup.exe')
        overlap=after['source']['coverage']['shared_entry_folders']
        self.assertEqual(overlap[0]['entry_ids'],['K23','I2'])
        self.assertEqual(after,self.run_disc())

    def test_exact_metadata_bytes_hash_sections_and_unknown_coverage_survive(self):
        self.tools.write_bytes(self.raw+b'[Future]\nUnknown=yes\n')
        (self.root/'Other.dtx').write_bytes(b'[X1]\nUnknown=yes\n')
        m=self.run_disc();s=m['source']['supplemental_metadata'][0]
        self.assertEqual(base64.b64decode(s['raw_base64']),self.tools.read_bytes())
        self.assertEqual(s['sha256'],hashlib.sha256(self.tools.read_bytes()).hexdigest())
        self.assertEqual(s['resolved_path'],'TOOLS.DTX');self.assertEqual(s['unprojected_sections'],['Future'])
        self.assertIn('Future',s['sections']);self.assertFalse(m['source']['coverage']['complete_disc'])
        self.assertEqual(m['source']['coverage']['unprocessed_metadata'],['Other.dtx'])
        self.assertTrue(any('Future' in w for w in m['source']['parser_warnings']))
        out=io.StringIO()
        with redirect_stdout(out):print_report(m,self.home/'manifest.json')
        self.assertIn('Other.dtx',out.getvalue());self.assertIn('2 poster',out.getvalue())

    def test_missing_norwegian_text_does_not_substitute_danish_or_rtf(self):
        self.tools.write_bytes(self.raw.replace('InstruksNo=Norsk omtale æøå.\r\n'.encode('cp1252'),b''))
        (self.root/'Tools/AdAware/No.rtf').write_bytes(b'{\\rtf1 unrelated fallback}')
        e=self.run_disc()['entries'][1]
        self.assertIsNone(e['normalized']['description']);self.assertIsNone(e['evidence']['description_tools']['text'])
        self.assertEqual(e['raw']['InstruksDK'],'Dansk tekst')

    def test_changed_metadata_after_inventory_is_rejected(self):
        self.tools.write_bytes(self.raw);inventory=build_inventory(self.root);self.tools.write_bytes(self.raw+b'\n')
        with self.assertRaisesRegex(ValueError,'Tools.dtx changed'):parse_disc(self.root,inventory)

    def test_bad_metadata_is_not_silently_ignored(self):
        for data in [b'not an ini',b'[I1]\nNavn=No folder\n',b'[I1]\nFolder=Tools/App\n']:
            with self.subTest(data=data):
                self.tools.write_bytes(data)
                with self.assertRaises((ValueError,configparser.Error)):self.run_disc()

    def test_unsafe_paths_are_rejected_and_missing_files_reported(self):
        for field in [b'Folder=../outside',b'Setup=/outside',b'Run=C:\\outside',b'Folder=.']:
            self.tools.write_bytes(b'[I1]\nNavn=Example\nFolder=Tools/App\n'+field+b'\n')
            with self.assertRaisesRegex(ValueError,'unsafe'):self.run_disc()
        self.tools.write_bytes(b'[I1]\nNavn=Example\nFolder=Tools/Missing\nSetup=Setup.exe\n')
        m=self.run_disc();self.assertFalse(m['validation']['valid'])
        self.assertEqual(m['validation']['missing_referenced_files'][0]['source_id'],'I1')

    def test_duplicate_metadata_warns_without_losing_original_bytes(self):
        data=self.raw+b'[I1]\nNavn=Last title\n';self.tools.write_bytes(data)
        m=self.run_disc();s=m['source']['supplemental_metadata'][0]
        self.assertEqual(len(m['entries']),3);self.assertEqual(m['entries'][1]['normalized']['title'],'Last title')
        self.assertEqual(base64.b64decode(s['raw_base64']),data)
        self.assertTrue(any('Duplicate' in w for w in m['source']['parser_warnings']))

    def test_extraction_retains_supplementary_metadata_and_source_ids(self):
        self.tools.write_bytes(self.raw);m=self.run_disc();out=self.home/'extract'
        extract_entries(self.root,m,out)
        import json
        d=json.loads((out/'extraction.json').read_text())
        self.assertEqual(d['source']['supplemental_metadata'],m['source']['supplemental_metadata'])
        self.assertEqual(len(d['entries']),3)
