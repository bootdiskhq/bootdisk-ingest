"""Bounded resource access for the D6 Afterburner (FGDM/FGDC) envelope.

The envelope is described by ScummVM's Director archive reader. Payloads retain
original resource IDs; no Lingo or installer is executed. This opt-in reader
also accepts a missing final RIFF alignment byte, only if all resources fit.
"""
import struct
import zlib
from functools import cached_property
from .archive import Archive, Resource, Key
from .binary import DirectorError, UnsupportedDirector, View


def varint(data, pos):
    value = 0
    for _ in range(5):
        if pos >= len(data):
            raise DirectorError('Truncated Afterburner integer')
        byte = data[pos]; pos += 1
        value = (value << 7) | (byte & 127)
        if not byte & 128:
            if value > 0xffffffff:
                raise DirectorError('Oversized Afterburner integer')
            return value, pos
    raise DirectorError('Oversized Afterburner integer')


def inflate(data, expected, maximum=128 * 1024 * 1024):
    if not 0 <= expected <= maximum:
        raise DirectorError('Afterburner expansion exceeds limit')
    try:
        obj = zlib.decompressobj()
        result = obj.decompress(data, expected + 1)
    except zlib.error as error:
        raise DirectorError('Invalid Afterburner zlib data') from error
    if len(result) != expected or not obj.eof or obj.unused_data or obj.unconsumed_tail:
        raise DirectorError('Afterburner expansion size or stream boundary mismatch')
    return result


class SourceArchive(Archive):
    def __init__(self, data):
        self._payloads = None
        self.missing_alignment_byte = False
        if data[8:12] not in (b'MDGF', b'CDGF'):
            # Some original CD casts omit just the terminal RIFF alignment byte.
            # Never pad a resource: the normal resource-bound checks still apply.
            if data[:4] == b'XFIR' and len(data) % 2 and int.from_bytes(data[4:8], 'little') + 8 == len(data) + 1:
                super().__init__(data + b'\0')
                if any(r.id != 0 and r.tag not in ('free','junk') and r.offset+r.size+8 > len(data) for r in self.resources):
                    raise DirectorError('Missing final resource byte, not alignment padding')
                self.data = bytes(data)
                self._v = View(self.data, 'archive', self.endian)
                self.missing_alignment_byte = True
            else:
                super().__init__(data)
            return
        if len(data) > self.MAX_FILE_SIZE or data[:4] != b'XFIR':
            raise UnsupportedDirector('Only bounded little-endian Afterburner supported')
        if int.from_bytes(data[4:8], 'little') + 8 != len(data):
            raise DirectorError('Afterburner container length mismatch')
        self.data = bytes(data); self.endian = '<'; self._v = View(self.data, 'archive', '<')
        pos = 12
        def chunk(tag):
            nonlocal pos
            if data[pos:pos+4] != tag[::-1]:
                raise DirectorError('Missing Afterburner chunk ' + tag.decode())
            pos += 4; size, pos = varint(data, pos)
            if pos + size > len(data):
                raise DirectorError('Truncated Afterburner chunk')
            result = data[pos:pos+size]; pos += size
            return result
        version = chunk(b'Fver'); ab_version, p = varint(version, 0)
        map_version, p = varint(version, p); self.version, p = varint(version, p)
        if ab_version != 0x500 or map_version != 1 or self.version != 0x04c7 or p != len(version):
            raise UnsupportedDirector('Unqualified Afterburner version')
        codecs = chunk(b'Fcdr')
        # Small codec table; verify its stream and the known first codec GUID.
        obj = zlib.decompressobj()
        try:
            codec_data = obj.decompress(codecs, 16385)
        except zlib.error as e:
            raise DirectorError('Invalid Afterburner codec table') from e
        if len(codec_data) > 16384 or not obj.eof or obj.unused_data or len(codec_data) < 18:
            raise DirectorError('Invalid Afterburner codec table')
        if codec_data[2:18] != bytes.fromhex('04e999ac7000360b0000080007377a34'):
            raise UnsupportedDirector('Unqualified Afterburner primary codec')
        codec_count = int.from_bytes(codec_data[:2], 'little')
        mapping = chunk(b'ABMP'); compression, p = varint(mapping, 0); size, p = varint(mapping, p)
        if compression != 0:
            raise UnsupportedDirector('Unknown map compression')
        mapping = inflate(mapping[p:], size); p = 0
        _, p = varint(mapping, p); _, p = varint(mapping, p); count, p = varint(mapping, p)
        if count > self.MAX_RESOURCES:
            raise DirectorError('Too many Afterburner resources')
        table = {}
        for _ in range(count):
            values = []
            for _ in range(5):
                value, p = varint(mapping, p); values.append(value)
            rid, offset, compressed, expanded, codec = values
            if p + 4 > len(mapping) or rid in table or rid >= self.MAX_RESOURCES or codec >= codec_count:
                raise DirectorError('Invalid Afterburner resource map')
            tag = mapping[p:p+4][::-1].decode('latin1'); p += 4
            table[rid] = (offset, compressed, expanded, codec, tag)
        if p != len(mapping) or 2 not in table or table[2][4] != 'ILS ':
            raise DirectorError('Invalid Afterburner map boundary/ILS')
        if data[pos:pos+4] != b'IEGF':
            raise DirectorError('Missing Afterburner FGEI')
        pos += 4; _, pos = varint(data, pos); base = pos
        _, size, expanded, codec, _ = table[2]
        if codec != 0:
            raise UnsupportedDirector('Unknown ILS compression')
        ils = inflate(data[pos:pos+size], expanded)
        payloads = {}; self._locations = {}; p = 0
        while p < len(ils):
            rid, p = varint(ils, p)
            if rid not in table or rid in payloads or table[rid][0] != 0xffffffff:
                raise DirectorError('Invalid ILS resource reference')
            n = table[rid][1]
            if p+n > len(ils):
                raise DirectorError('Truncated ILS resource')
            payloads[rid] = ils[p:p+n]
            self._locations[rid] = {'compression':'zlib','offset':base,'compressed_size':size,'expanded_size':len(ils),'payload_offset':p}
            p += n
        self._payloads = payloads; self._compressed = table; self._base = base
        self.resources = tuple(Resource(i, table[i][4], table[i][2], table[i][0], 0)
                               if i in table else Resource(i, 'free', 0, 0, 0)
                               for i in range(max(table)+1))
        for rid, (offset, size, expanded, codec, tag) in table.items():
            if expanded > self.MAX_FILE_SIZE:
                raise DirectorError('Oversized Afterburner resource')
            if offset != 0xffffffff and base+offset+size > len(data):
                raise DirectorError('Afterburner resource exceeds source')
            if offset == 0xffffffff and rid not in payloads:
                raise DirectorError('Missing ILS resource')

    def payload(self, resource_id, expected=None):
        if self._payloads is None:
            return super().payload(resource_id, expected)
        self.resource(resource_id, expected)
        if resource_id not in self._payloads:
            offset, size, expanded, codec, _ = self._compressed[resource_id]
            raw = self.data[self._base+offset:self._base+offset+size]
            if codec == 0:
                raw = inflate(raw, expanded)
            else:
                raise UnsupportedDirector('Unsupported compressed resource codec')
            self._payloads[resource_id] = raw
        return self._payloads[resource_id]

    @cached_property
    def _keys(self):
        if self._payloads is None:
            return super().keys()
        result = []
        self.omitted_key_references = []
        for rid in self.ids('KEY*'):
            v = View(self.payload(rid), 'Afterburner KEY*', self.endian)
            stride, capacity, count = v.u16(0), v.u32(4), v.u32(8)
            v.require(stride == 12 and v.u16(2) == 12 and count <= capacity, 0, 'invalid key table')
            v.table(12, capacity, stride)
            for p in v.table(12, count, stride):
                child, parent = v.u32(p), v.u32(p+4)
                tag = v.span(p+8, 4)[::-1].decode('latin1')
                if child >= len(self.resources) or self.resources[child].tag == 'free':
                    if tag not in ('THUM', 'sndH', 'sndS', 'SCRF'):
                        raise DirectorError('Missing non-optional Afterburner key target')
                    self.omitted_key_references.append(Key(child, parent, tag))
                    continue
                self.resource(child, tag)
                result.append(Key(child, parent, tag))
        return tuple(result)

    def keys(self):
        return self._keys
