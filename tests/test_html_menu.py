import unittest
from bootdisk_ingest.adapters.kcd.html_menu import index_rows,parse_page,local_path

PAGE='''<meta content="text/html; charset=iso-8859-1"><div id="content"><h1>Prøve</h1><ul class="softwaredetails"><li>Versjon: 2.1</li><li>Lisenstype: Gratis</li></ul><p class="softwaredesc">Original &amp; norsk.<br>Andre linje.</p><img class="softwareimage" src="../topical/01/image.jpg"><a href="../topical/01/setup.exe">Installer</a></div>'''.encode('latin1')
ROW={'title':'Prøve','url':'html/topical01.html','category':'topical'}
class HtmlTest(unittest.TestCase):
 def test_fields_and_source_links(self):
  r=parse_page(PAGE,ROW);self.assertEqual(r['description'],'Original & norsk.\nAndre linje.');self.assertEqual(r['references'],['topical/01/setup.exe']);self.assertEqual(r['version'],'2.1');self.assertEqual(r['license'],'Gratis')
 def test_html_latin1_label_uses_windows_1252(self):
  self.assertIn("–",parse_page(PAGE.replace(b"Original",b"Original \x96"),ROW)["description"])
 def test_index_never_executes(self):
  with self.assertRaises(ValueError):index_rows(b'var cdindex = new Array(); alert(1);')
 def test_index_requires_contiguous_rows(self):
  with self.assertRaises(ValueError):index_rows(b'''var cdindex = new Array();cdindex[1] = { 'title':"x", 'url':'html/x.html', 'category':'topical' };''')
 def test_title_mismatch(self):
  with self.assertRaises(ValueError):parse_page(PAGE,dict(ROW,title='Other'))
 def test_trailing_editorial_space(self):self.assertEqual(parse_page(PAGE,dict(ROW,title='Prøve '))['title'],'Prøve')
 def test_escape_rejected(self):
  for href in ['../../outside.exe','/%2fetc/passwd','..\\outside']:
   with self.assertRaises(ValueError):local_path('html/x.html',href)
 def test_external_not_local(self):self.assertIsNone(local_path('html/x.html','https://example.com/a'))
 def test_unknown_control_rejected(self):
  with self.assertRaises(ValueError):parse_page(PAGE.replace(b'</div>',b'<input onclick="evil()"></div>'),ROW)
 def test_duplicate_field_rejected(self):
  with self.assertRaises(ValueError):parse_page(PAGE.replace(b'</ul>',b'<li>Versjon: 3</li></ul>'),ROW)
 def test_grouped_article_text_excludes_download_label(self):
  page=b'''<meta content="charset=iso-8859-1"><div class="guide"><img src="../pdfarticle/01/image.jpg"><p class="guideheadline">Article</p><p class="guidedesc">Original.<br><input onclick="window.open('../pdfarticle/01/article.html')"><span><a onclick="window.open('../pdfarticle/01/a.pdf')">Download</a></span></p></div>'''
  r=parse_page(page,{'title':'Article','category':'articles','url':'html/articles.html'});self.assertEqual(r['description'],'Original.');self.assertEqual(len(r['references']),2)
if __name__=='__main__':unittest.main()
