"""K-CD 9/2000: qualify real source links, never execute the programs."""
import json,os,tempfile,unittest
from pathlib import Path
from bootdisk_ingest.feature_sections import observe,qualify
from bootdisk_ingest.workshop_images import extract

@unittest.skipUnless(os.environ.get('BOOTDISK_FEATURE_KCD9_INVENTORY'), 'Mounted K-CD 9/2000 inventory required')
class Kcd9Features(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.context={}
  cls.manifest=observe('/Volumes/K-CD 9-2000',os.environ['BOOTDISK_FEATURE_KCD9_INVENTORY'],context=cls.context,medium='kcd-9-2000')
 def qualify(self,inventory=None,medium='kcd-9-2000'):
  return qualify(self.context['workshop'],inventory or self.manifest['file_inventory'],Path('/Volumes/K-CD 9-2000'),medium=medium)
 def test_source_titles_targets_and_explicit_menu_version(self):
  entries=self.manifest['entries']
  self.assertEqual([e['normalized']['title'] for e in entries],['Bubblet!','PhotoPrinter','MCP Mouse Milage'])
  self.assertEqual([e['files']['referenced']['launch']['path'].casefold() for e in entries],['bubblet/setup.exe','photoprinter/setup.exe','mouse milage/mcpmm.exe'])
  self.assertIn('2.0 LE',entries[1]['evidence']['menu_title']['text']['cp1252_view'])
  self.assertTrue(all(e['normalized']['description'] and e['normalized']['version'] is None for e in entries))
 def test_stale_support_control_is_retained_not_a_fourth_program(self):
  entry=self.manifest['entries'][2]
  stale=[c for c in entry['evidence']['other_launch_controls'] if c['channel']==49]
  self.assertEqual(len(stale),1)
  self.assertEqual(stale[0]['path'].casefold(),'fontpage/vbrun60.exe')
  self.assertEqual(stale[0]['inventory_matches'],[])
  self.assertIn('missing_auxiliary_launch_file',entry['issues'])
  self.assertEqual(len(self.manifest['entries']),3)
 def test_missing_program_file_is_rejected(self):
  inv=[f for f in self.manifest['file_inventory'] if f['path'].casefold()!='bubblet/setup.exe']
  with self.assertRaisesRegex(ValueError,'Missing or ambiguous source file'):self.qualify(inv)
 def test_wrong_profile_is_rejected(self):
  with self.assertRaisesRegex(ValueError,'title/description'):self.qualify(medium='kcd-4-2000')
 def test_three_source_illustrations(self):
  with tempfile.TemporaryDirectory() as tmp:
   p=Path(tmp)/'manifest.json';p.write_text(json.dumps(self.manifest))
   report=extract(p,self.context,Path(tmp)/'images',selection_rule='original section illustration')
   self.assertEqual(len(report['assets']),3)
