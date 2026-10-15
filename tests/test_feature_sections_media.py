"""Checks against read-only mounted media; no historical program is executed."""
import copy
import importlib.util
from pathlib import Path
import unittest
from unittest.mock import patch

import os
from bootdisk_ingest import feature_sections as m
from bootdisk_ingest.legacy_tools import observe

@unittest.skipUnless(os.environ.get('BOOTDISK_FEATURE_INVENTORY'), 'Set BOOTDISK_FEATURE_INVENTORY for mounted-media checks')
class FeaturedChecks(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  context={}
  manifest=observe('/Volumes/KCD_1_2000',os.environ['BOOTDISK_FEATURE_INVENTORY'],context=context)
  cls.env={'w':context['workshop'],'manifest':manifest,'root':Path('/Volumes/KCD_1_2000')}
 def qualify(self,inventory=None):
  return m.qualify(self.env['w'],inventory if inventory is not None else self.env['manifest']['file_inventory'],self.env['root'])
 def test_three_original_titles_and_other_controls_retained(self):
  rows=self.qualify()
  self.assertEqual([r['normalized']['title'] for r in rows],['Toonworks','PicturesToExe','WindowBlinds'])
  for r in rows:
   self.assertTrue(r['normalized']['description'])
   self.assertIsNone(r['normalized']['version'])
   self.assertEqual(r['evidence']['warning_continue']['channel'],91)
   others=r['evidence']['other_launch_controls']
   self.assertEqual(len(others),1)
   self.assertEqual(others[0]['channel'],16)
   self.assertEqual(others[0]['path'].casefold(),'heart/setup.exe')
 def test_missing_main_navigation_rejected(self):
  labels=copy.deepcopy(self.env['w'].labels);labels.pop(b'Knap2')
  with patch.object(self.env['w'],'labels',labels),self.assertRaises(ValueError):self.qualify()
 def test_ambiguous_section_rejected(self):
  labels=copy.deepcopy(self.env['w'].labels);labels[b'Edutainment'].append(95)
  with patch.object(self.env['w'],'labels',labels),self.assertRaises(ValueError):self.qualify()
 def test_source_hash_mismatch_rejected(self):
  inv=copy.deepcopy(self.env['manifest']['file_inventory'])
  next(f for f in inv if f['path'].casefold()=='toonworks/tw_demo.exe')['sha256']='0'*64
  with self.assertRaisesRegex(ValueError,'Source file changed'):self.qualify(inv)
 def test_missing_original_title_rejected(self):
  with patch.object(self.env['w'],'text',return_value=None),self.assertRaisesRegex(ValueError,'title/description'):self.qualify()

 def test_warning_specific_control_required(self):
  links=self.env['w'].links
  original=links.resolve
  def resolve(sprite):
   if sprite.channel==91:return None
   return original(sprite)
  with patch.object(links,'resolve',side_effect=resolve),self.assertRaisesRegex(ValueError,'launch button'):self.qualify()
 def test_additive_manifest_and_three_preserved_illustrations(self):
  import tempfile
  import json
  from bootdisk_ingest.workshop_images import extract
  context={}
  manifest=m.observe(self.env['root'],os.environ['BOOTDISK_FEATURE_INVENTORY'],context=context)
  self.assertEqual(len(manifest['entries']),3)
  self.assertFalse(manifest['validation']['valid'])
  self.assertTrue(all(e['issues']==['shared_warning_control_not_runtime_tested'] for e in manifest['entries']))
  with tempfile.TemporaryDirectory() as temp:
   path=Path(temp)/'manifest.json';path.write_text(json.dumps(manifest))
   report=extract(path,context,Path(temp)/'images',selection_rule='original section illustration')
   self.assertEqual(len(report['assets']),3)
   self.assertTrue(all(a['selection']['rule']=='original section illustration' for a in report['assets']))

if __name__=='__main__':unittest.main()
