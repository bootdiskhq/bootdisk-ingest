"""Explicit K-CD 4/2000 profile; source media is read, never executed."""
import json
import os
from pathlib import Path
import tempfile
import unittest
from bootdisk_ingest.feature_sections import observe
from bootdisk_ingest.workshop_images import extract

@unittest.skipUnless(os.environ.get('BOOTDISK_FEATURE_KCD4_INVENTORY'), 'Mounted K-CD 4/2000 inventory required')
class Kcd4Features(unittest.TestCase):
 def test_titles_launches_support_control_and_artwork(self):
  context={};m=observe('/Volumes/K-CD 4-2000',os.environ['BOOTDISK_FEATURE_KCD4_INVENTORY'],context=context,medium='kcd-4-2000')
  self.assertEqual([e['normalized']['title'] for e in m['entries']],['Animated Memory','Home Gene Splicing','FontPage'])
  self.assertEqual([e['files']['referenced']['launch']['path'].casefold() for e in m['entries']],['memory/setup.exe','genes/genesplicer.exe','fontpage/setup.exe'])
  font=m['entries'][2]
  self.assertEqual({c['path'].casefold() for c in font['evidence']['other_launch_controls']},{'heart/setup.exe','fontpage/vbrun60.exe'})
  self.assertEqual(len(m['entries']),3) # Runtime is evidence, not an invented fourth post.
  with tempfile.TemporaryDirectory() as tmp:
   p=Path(tmp)/'manifest.json';p.write_text(json.dumps(m))
   images=extract(p,context,Path(tmp)/'images',selection_rule='original section illustration')
   self.assertEqual(len(images['assets']),3)
 def test_wrong_medium_does_not_relabel_sources(self):
  with self.assertRaisesRegex(ValueError,'title/description'):
   observe('/Volumes/K-CD 4-2000',os.environ['BOOTDISK_FEATURE_KCD4_INVENTORY'],medium='kcd-1-2000')
