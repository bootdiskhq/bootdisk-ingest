import struct
import unittest
import zlib
from types import SimpleNamespace as N
from bootdisk_ingest.formats.director.afterburner import SourceArchive, inflate, varint
from bootdisk_ingest.formats.director import DirectorError
from bootdisk_ingest.legacy_tools import properties, literal_string, consumes_property
from tests.director_fixtures import archive


def vi(value):
    values=[value&127];value>>=7
    while value:values.append((value&127)|128);value>>=7
    return bytes(reversed(values))


def compressed_archive(payload=b'original data', duplicate=False):
    ils=vi(3)+payload
    if duplicate:ils+=vi(3)+payload
    packed=zlib.compress(ils)
    table=vi(1)+vi(3)+vi(2)
    for rid,off,size,expanded,codec,tag in [(2,0,len(packed),len(ils),0,b'ILS '),(3,0xffffffff,len(payload),len(payload),0,b'TEST')]:
        table+=b''.join(vi(v) for v in (rid,off,size,expanded,codec))+tag[::-1]
    def chunk(tag,p):return tag[::-1]+vi(len(p))+p
    body=chunk(b'Fver',vi(0x500)+vi(1)+vi(0x4c7))
    body+=chunk(b'Fcdr',zlib.compress(struct.pack('<H',1)+bytes.fromhex('04e999ac7000360b0000080007377a34')))
    body+=chunk(b'ABMP',vi(0)+vi(len(table))+zlib.compress(table))
    body+=b'IEGF'+vi(0)+packed
    return b'XFIR'+struct.pack('<I',len(body)+4)+b'MDGF'+body

class AfterburnerTests(unittest.TestCase):
    def test_preserves_original_container_and_resource(self):
        raw=compressed_archive();a=SourceArchive(raw)
        self.assertEqual(a.data,raw)
        self.assertEqual(a.payload(3,'TEST'),b'original data')
        self.assertEqual(a._locations[3]['payload_offset'],1)

    def test_rejects_bad_stream_boundaries_and_duplicates(self):
        for raw in [compressed_archive()[:-1],compressed_archive()+b'x',compressed_archive(duplicate=True)]:
            with self.subTest(size=len(raw)),self.assertRaises(DirectorError):SourceArchive(raw)
        for raw,n in [(zlib.compress(b'abcd'),3),(zlib.compress(b'abcd')+b'extra',4),(b'bad',4)]:
            with self.assertRaises(DirectorError):inflate(raw,n)

    def test_varint_bounds(self):
        self.assertEqual(varint(vi(0xffffffff),0),(0xffffffff,5))
        for raw in [b'\x80',b'\xff'*6]:
            with self.assertRaises(DirectorError):varint(raw,0)

    def test_missing_alignment_byte_is_not_missing_content(self):
        raw=archive([('TEST',b'abc')])
        a=SourceArchive(raw[:-1]);self.assertTrue(a.missing_alignment_byte)
        self.assertEqual(a.data,raw[:-1]);self.assertEqual(a.payload(3),b'abc')
        with self.assertRaises(DirectorError):SourceArchive(raw[:-3])
        even=archive([('TEST',b'abcd')])
        with self.assertRaises(DirectorError):SourceArchive(even[:-1])

class InitializerTests(unittest.TestCase):
    def test_literal_command_not_execution(self):
        raw=b'[#TargetSprite: 1, #correctCommand: "go to frame " & QUOTE & "Some Tool" & QUOTE, #IncorrectCommand: "do nothing"]\0\0'
        p=properties(raw)
        self.assertEqual(literal_string(p['correctcommand']),'go to frame "Some Tool"')
        self.assertEqual(literal_string('"Tools\\Setup.exe"'),'Tools\\Setup.exe')
        for bad in ['the moviePath & "run"','"x" & evil()','QUOTE junk']:
            with self.assertRaises(DirectorError):literal_string(bad)

    def test_duplicate_and_broken_properties_rejected(self):
        for raw in [b'[#A: "x", #a: "y"]',b'[#A: "oops]',b'not a list']:
            with self.assertRaises(DirectorError):properties(raw)

    def test_requires_property_use_in_mouseup_handler(self):
        code=[N(opcode=0x61,operand=0),N(opcode=0x42,operand=1),N(opcode=0x57,operand=1)]
        script=N(names=(b'correctCommand',b'do'),handlers=[N(name=b'mouseUp',instructions=code)])
        self.assertTrue(consumes_property(script,'correctcommand'))
        self.assertFalse(consumes_property(script,'runcommand'))
        script.handlers[0].name=b'getPropertyDescriptionList'
        self.assertFalse(consumes_property(script,'correctcommand'))
