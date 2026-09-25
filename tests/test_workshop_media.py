"""Opt-in acceptance against mounted original media, never bundled CD bytes."""
import json
import os
from pathlib import Path
import tempfile
import unittest
from bootdisk_ingest.legacy_tools import observe
from bootdisk_ingest.workshop_images import extract

@unittest.skipUnless(os.environ.get('BOOTDISK_WORKSHOP_INVENTORIES'),'Set BOOTDISK_WORKSHOP_INVENTORIES for mounted-media qualification')
class WorkshopMediaTests(unittest.TestCase):
    def test_six_qualified_shelves_and_artworks(self):
        inventories=Path(os.environ['BOOTDISK_WORKSHOP_INVENTORIES'])
        for disc,volume,count,issues in [('1-2000','KCD_1_2000',22,0),('4-2000','K-CD 4-2000',25,1),('9-2000','K-CD 9-2000',25,0),('13-2000','KCD_13_2000',28,0),('1-2001','K-CD 1-2001',29,1),('8-2001','K-CD 8-2001',33,0)]:
            with self.subTest(disc=disc),tempfile.TemporaryDirectory() as tmp:
                context={};result=observe(Path('/Volumes')/volume,inventories/('kcd-'+disc+'-fresh.json'),context=context)
                self.assertEqual(len(result['entries']),count)
                self.assertEqual(len(result['validation']['entry_issues']),issues)
                self.assertEqual(len({e['source_id'] for e in result['entries']}),count)
                self.assertTrue(all(e['normalized']['description'] for e in result['entries']))
                manifest=Path(tmp)/'manifest.json';manifest.write_text(json.dumps(result))
                report=extract(manifest,context,Path(tmp)/'images')
                self.assertEqual(len(report['assets']),count)
                self.assertTrue(all(e['source_id'] in {a['entry_source_id'] for a in report['assets']} for e in result['entries']))
