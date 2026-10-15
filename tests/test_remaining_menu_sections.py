import copy,json,os,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from bootdisk_ingest import menu_sections as m, feature_sections as f, special_section as s
class SafeResolution(unittest.TestCase):
 def test_no_drive_control_or_basename_repair(self):
  for bad in ['D:/Arkivet/Acro32.exe','Arkivet/Acro32.exe\x1b','Acro32.exe','../Acro32.exe']:
   self.assertIsNone(m.resolve_file(bad,[{'path':'Arkivet/Acro32.exe','size':0,'sha256':'x'}],Path('/tmp')))
 def test_ambiguous_case_is_rejected(self):
  with self.assertRaisesRegex(ValueError,'Ambiguous'):m.resolve_file('X.exe',[{'path':'X.exe'},{'path':'x.exe'}],Path('/tmp'))
@unittest.skipUnless(os.environ.get('BOOTDISK_REMAINING_INVENTORIES'),'Mounted media inventories required')
class RemainingMenus(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.root=Path(os.environ['BOOTDISK_REMAINING_INVENTORIES']);cls.observed={}
  for med,mount in [('kcd-1-2000','KCD_1_2000'),('kcd-4-2000','K-CD 4-2000'),('kcd-9-2000','K-CD 9-2000'),('kcd-13-2000','KCD_13_2000')]:
   c={};root=Path('/Volumes')/mount;r=m.observe(root,cls.root/(med+'.json'),medium=med,context=c);cls.observed[med]=(r,c,root)
 def test_all_44_titles_and_literal_files(self):
  for med,(r,_,_) in self.observed.items():
   self.assertEqual(len(r['entries']),11);self.assertEqual(len({e['source_id'] for e in r['entries']}),11)
   self.assertTrue(all(e['normalized']['title'] and e['normalized']['description'] for e in r['entries']))
   self.assertEqual(sum(bool(e['issues']) for e in r['entries']),int(med=='kcd-13-2000'))
 def test_guides_bind_pdf_not_reader(self):
  for r,_,_ in self.observed.values():
   for e in r['entries'][6:]:
    self.assertTrue(e['files']['referenced']['launch']['path'].lower().endswith('.pdf'));self.assertNotIn('acro32',str(e['files']).lower())
 def test_marble_both_controls_without_repair(self):
  e=self.observed['kcd-13-2000'][0]['entries'][5]
  self.assertTrue(e['evidence']['primary_launch']['path'].endswith('\x1b'*6))
  self.assertEqual(e['evidence']['warning_continue']['path'],'MarbleJongg/Marbjong.exe')
  self.assertNotIn('launch',e['files']['referenced']);self.assertIn('warning_launch',e['files']['referenced']);self.assertIn('conflicting_launch_targets',e['issues'])
 def test_wrong_disc_rejected(self):
  r,c,root=self.observed['kcd-1-2000']
  with self.assertRaisesRegex(ValueError,'Wrong classic'):m.qualify(c['workshop'],r['file_inventory'],root,'kcd-4-2000')
 def test_missing_navigation_rejected(self):
  r,c,root=self.observed['kcd-1-2000'];w=c['workshop'];labels=copy.deepcopy(w.labels);labels.pop(b'Knap4')
  with patch.object(w,'labels',labels),self.assertRaises(ValueError):m.qualify(w,r['file_inventory'],root,'kcd-1-2000')
 def test_changed_file_rejected(self):
  r,c,root=self.observed['kcd-1-2000'];inv=copy.deepcopy(r['file_inventory']);next(x for x in inv if x['path'].casefold()=='arkivet/pl32.exe')['sha256']='0'*64
  with self.assertRaisesRegex(ValueError,'Source file changed'):m.qualify(c['workshop'],inv,root,'kcd-1-2000')
 def test_feature13(self):
  r=f.observe('/Volumes/KCD_13_2000',self.root/'kcd-13-2000.json',medium='kcd-13-2000')
  self.assertEqual([e['normalized']['title'] for e in r['entries']],['Nerf ArenaBlast','Adastra','Audio Notes Recorder']);self.assertIn('missing_auxiliary_launch_file',r['entries'][2]['issues'])
@unittest.skipUnless(os.environ.get('BOOTDISK_SPECIAL_MANIFEST'),'Mounted special section required')
class SpecialSection(unittest.TestCase):
 def test_no_invented_installer(self):
  e=s.observe('/Volumes/K-CD 15 2001',os.environ['BOOTDISK_SPECIAL_MANIFEST'])['entries'][0]
  self.assertEqual(e['normalized']['title'],'PC-ens driftsutgifter');self.assertIsNone(e['normalized']['installer']);self.assertIsNone(e['normalized']['run']);self.assertEqual(e['files']['referenced'],{});self.assertEqual(set(e['files']['discovered']),{'icon','screenshot'})
 def test_no_special_metadata_no_post(self):
  r=json.loads(Path(os.environ['BOOTDISK_SPECIAL_MANIFEST']).read_text());r['source']['sections']['Generelt'].pop('Speciel')
  with tempfile.TemporaryDirectory() as tmp:
   p=Path(tmp)/'manifest.json';p.write_text(json.dumps(r))
   with self.assertRaisesRegex(ValueError,'Unsupported'):s.observe('/Volumes/K-CD 15 2001',p)
