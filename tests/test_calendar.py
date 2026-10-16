import tempfile
from pathlib import Path
import unittest
from bootdisk_ingest.pipeline import ingest_kcd

class CalendarTests(unittest.TestCase):
    def make(self, root, extra=''):
        (root/'K.DTX').write_text('[Generelt]\nSprog=Norsk\n[K1]\nTitel=Main\nFolder=Main\n')
        (root/'J.DTX').write_text('[Generelt]\nSprog=Norsk\n[J1]\nTitel=Calendar\nFolder=01\nSetup=Game.exe\nType=3\n'+extra)
        (root/'01').mkdir();(root/'01/Game.exe').write_bytes(b'fixture')
        (root/'01/No.rtf').write_bytes(b'{\\rtf1\\ansi Original calendar text.}')
    def test_calendar_and_rtf_are_included(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);self.make(root);m=ingest_kcd(root)
            e=next(e for e in m['entries'] if e['source_id']=='J1')
            self.assertEqual(e['raw']['Type'],'3');self.assertEqual(e['normalized']['categories'],[])
            self.assertEqual(e['evidence']['description_rtf']['text'],'Original calendar text.')
            self.assertEqual(m['source']['coverage']['unprocessed_metadata'],[])
            self.assertEqual(e['evidence']['calendar_metadata']['path'],'J.DTX')
    def test_missing_target_is_preserved(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);self.make(root);(root/'01/Game.exe').unlink();m=ingest_kcd(root)
            self.assertFalse(next(e for e in m['entries'] if e['source_id']=='J1')['files']['referenced']['installer']['exists'])
    def test_unsafe_path_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);self.make(root);p=root/'J.DTX';p.write_text(p.read_text().replace('Folder=01','Folder=../outside'))
            with self.assertRaises(ValueError):ingest_kcd(root)
    def test_unknown_sections_remain_visible(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);self.make(root,'\n[Other]\nTitel=Unknown\n');m=ingest_kcd(root)
            self.assertEqual(m['source']['coverage']['metadata_files'][-1]['unprojected_sections'],['Other'])
    def test_no_calendar_does_not_change_primary_entries(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);self.make(root);with_calendar=ingest_kcd(root);(root/'J.DTX').unlink();without=ingest_kcd(root)
            self.assertEqual(with_calendar['entries'][0],without['entries'][0])
