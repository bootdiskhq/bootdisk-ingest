import json
import hashlib
from pathlib import Path
import tempfile
import unittest
from bootdisk_ingest.rtf_documents import collect


class RtfDocumentTests(unittest.TestCase):
    def test_menu_text_does_not_hide_original_and_source_is_unchanged(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);raw=b'{\\rtf1 Original\\par More}\r\n\x00';(root/'No.rtf').write_bytes(raw)
            file={'path':'No.rtf','exists':True,'sha256':hashlib.sha256(raw).hexdigest(),'size':len(raw)}
            m={'entries':[{'source_id':'K1','raw':{'Global':'Short'},'files':{'discovered':{'description_rtf':file}}}], 'file_inventory':[file]}
            path=root/'manifest.json';path.write_text(json.dumps(m));before=path.read_bytes()
            result=collect(path,root);self.assertEqual(result['documents'][0]['text'],'Original\nMore')
            self.assertEqual(path.read_bytes(),before);self.assertEqual((root/'No.rtf').read_bytes(),raw)
            (root/'No.rtf').write_bytes(b'changed')
            with self.assertRaisesRegex(ValueError,'changed'): collect(path,root)

    def test_escape_fails_and_unsupported_source_retains_original(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);raw=b'unsupported';(root/'No.rtf').write_bytes(raw)
            file={'path':'No.rtf','exists':True,'sha256':hashlib.sha256(raw).hexdigest(),'size':len(raw)}
            m={'entries':[{'source_id':'K1','files':{'discovered':{'description_rtf':file}}}], 'file_inventory':[dict(file)]}
            p=root/'m.json';p.write_text(json.dumps(m));doc=collect(p,root)['documents'][0]
            self.assertIsNone(doc['text']);self.assertTrue(doc['warning']);self.assertTrue(doc['raw_base64'])
            file['resolved_path']='../secret.rtf';p.write_text(json.dumps(m))
            with self.assertRaisesRegex(ValueError,'unsafe'): collect(p,root)
