import json
import os
from pathlib import Path
import struct
import tempfile
from types import SimpleNamespace as NS
import unittest
from bootdisk_ingest.director_images import bitmap_layout, select_images, extract
from bootdisk_ingest.formats.director import DirectorError


def metadata(w,h):
    data=bytearray(28);struct.pack_into('>Hhhhh',data,0,0x8000+w,0,0,h,w);data[23]=8;struct.pack_into('>hh',data,24,0,178);return bytes(data)

def sprite(channel,w,h,y=100):
    raw=bytearray(24);struct.pack_into('>hhHH',raw,12,y,59,60,250)
    s=NS(channel=channel,kind=1,raw=bytes(raw));s.link=NS(cast=NS(kind=1,data=metadata(w,h)))
    return s

class ImageSelectionTests(unittest.TestCase):
    def test_layout_rejects_truncation_and_bad_dimensions(self):
        self.assertEqual(bitmap_layout(metadata(195,145))['width'],195)
        for raw in (b'',metadata(0,145),metadata(195,0),metadata(195,145)[:27]):
            with self.assertRaises(DirectorError):bitmap_layout(raw)

    def test_selects_unique_detail_and_title_row_not_other_icon(self):
        title=sprite(8,1,1,84);title.link.cast.kind=12
        good=sprite(24,32,32,107);other=sprite(25,32,32,168)
        frames=[NS(number=1,sprites=[title,good,other]),NS(number=2,sprites=[sprite(9,195,145),sprite(5,640,480)])]
        entry={'evidence':{'selection':{'frame':1,'channel':8,'method':'clickable menu text'},'frame_action':{'frame':2}}}
        selected,issues=select_images(entry,frames,NS(resolve=lambda s:s.link))
        self.assertEqual([s[0] for s in selected],['screenshot','icon']);self.assertIs(selected[1][2],good);self.assertEqual(issues,[])
        frames[0].sprites.append(sprite(26,32,32,108))
        selected,issues=select_images(entry,frames,NS(resolve=lambda s:s.link))
        self.assertEqual([s[0] for s in selected],['screenshot']);self.assertIn('missing_or_ambiguous_menu_icon',issues)

    def test_ambiguous_detail_is_never_chosen(self):
        frame=NS(number=1,sprites=[sprite(8,195,145),sprite(9,195,145)])
        entry={'evidence':{'selection':{'method':'game'},'frame_action':{'frame':1}}}
        selected,issues=select_images(entry,[frame],NS(resolve=lambda s:s.link))
        self.assertEqual(selected,[]);self.assertIn('missing_or_ambiguous_detail_image',issues)

    @unittest.skipUnless(os.environ.get('BOOTDISK_IMAGE_MANIFEST') and os.environ.get('BOOTDISK_DIRECTOR_FIXTURES'),'image media and manifest unavailable')
    def test_real_disc_has_21_images_and_18_icons_and_rejects_changed_binding(self):
        source=os.environ['BOOTDISK_DIRECTOR_FIXTURES'];manifest=Path(os.environ['BOOTDISK_IMAGE_MANIFEST'])
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);result=extract(manifest,source,root/'one')
            self.assertEqual(sum(a['kind']=='screenshot' for a in result['assets']),21)
            self.assertEqual(sum(a['kind']=='icon' for a in result['assets']),18)
            self.assertEqual(result,extract(manifest,source,root/'two'))
            with self.assertRaisesRegex(DirectorError,'new directory'):extract(manifest,source,root/'one')
            m=json.loads(manifest.read_bytes());m['entries'][0]['evidence']['frame_action']['frame']+=1
            changed=root/'manifest.json';changed.write_text(json.dumps(m))
            with self.assertRaisesRegex(DirectorError,'binding mismatch'):extract(changed,source,root/'bad')
