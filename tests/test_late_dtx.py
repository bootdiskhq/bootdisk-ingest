import unittest
from bootdisk_ingest.adapters.kcd.late_dtx import occurrences,late_entries
class OccurrenceTests(unittest.TestCase):
 def test_duplicate_sections_do_not_inherit_previous_fields(self):
  blocks=occurrences('[K36]\r\nTitel=Pixia\r\nEkstra=help.exe\r\n[K36]\r\nTitel=Browser\r\n')
  self.assertEqual(blocks['K36'],[{'Titel':'Pixia','Ekstra':'help.exe'},{'Titel':'Browser'}])
 def test_unqualified_disc_is_not_rewritten(self):
  entries=[];self.assertEqual(late_entries('.',{'files':[]},'unknown','[Flytter]\nTitel=X',{},entries),[])
  self.assertEqual(entries,[])
