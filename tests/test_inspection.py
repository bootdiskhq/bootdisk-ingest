import base64
import hashlib
import json
from pathlib import Path
import struct
import tempfile
import unittest
from unittest.mock import patch

from bootdisk_ingest.formats.pe_version import PEError, version_observations
from bootdisk_ingest.inspection import inspect_bytes, inspect_file, inspect_manifest, main


def align(data):
    return data + b"\0" * (-len(data) % 4)


def block(key, value=b"", children=(), kind=1):
    header = struct.pack("<HHH", 0, len(value) // 2 if kind else len(value), kind)
    payload = align(header + (key + "\0").encode("utf-16le")) + value
    for child in children:
        payload = align(payload) + child
    return struct.pack("<H", len(payload)) + payload[2:]


def version_blob(product="Generic Installer", version="1.0"):
    strings = block("040904b0", children=[
        block("ProductName", (product + "\0").encode("utf-16le")),
        block("ProductVersion", (version + "\0").encode("utf-16le"))])
    fixed = struct.pack("<13I", 0xfeef04bd, 0x10000, 0x10002, 0x30004, 0x50006, 0x70008, 0, 0, 0, 0, 0, 0, 0)
    return block("VS_VERSION_INFO", fixed, [block("StringFileInfo", children=[strings])], kind=0)


def pe_image(blobs=None, plus=False):
    blobs = [version_blob()] if blobs is None else blobs
    n = len(blobs)
    # Type 16 -> name 1 -> all supplied language resources.
    data_start = 64 + n * 8 + n * 16
    resource = bytearray(data_start)
    for off, count in ((0, 1), (24, 1), (48, n)):
        struct.pack_into("<HH", resource, off + 12, 0, count)
    struct.pack_into("<II", resource, 16, 16, 0x80000018)
    struct.pack_into("<II", resource, 40, 1, 0x80000030)
    for index, blob in enumerate(blobs):
        leaf = 64 + n * 8 + index * 16
        struct.pack_into("<II", resource, 64 + index * 8, 1033 + index, leaf)
        struct.pack_into("<IIII", resource, leaf, 0x1000 + len(resource), len(blob), 0, 0)
        resource.extend(blob)
        resource = bytearray(align(resource))
    raw_size = (len(resource) + 511) & ~511
    image = bytearray(512 + raw_size)
    image[:2] = b"MZ"; struct.pack_into("<I", image, 60, 128)
    image[128:132] = b"PE\0\0"
    optional_size = 240 if plus else 224
    struct.pack_into("<H", image, 134, 1)
    struct.pack_into("<H", image, 148, optional_size)
    struct.pack_into("<H", image, 152, 0x20b if plus else 0x10b)
    directory_offset = 112 if plus else 96
    struct.pack_into("<I", image, 152 + directory_offset - 4, 16)
    struct.pack_into("<II", image, 152 + directory_offset + 16, 0x1000, len(resource))
    section = 152 + optional_size
    image[section:section + 8] = b".rsrc\0\0\0"
    struct.pack_into("<IIII", image, section + 8, len(resource), 0x1000, raw_size, 512)
    image[512:512 + len(resource)] = resource
    return bytes(image)


class VersionTests(unittest.TestCase):
    def test_pe32_and_pe32plus_read_structural_version_fields(self):
        for plus in (False, True):
            data = pe_image(plus=plus)
            result = version_observations(data)
            fields = {o['field']: o['value'] for o in result['observations']}
            self.assertEqual(result['status'], 'observed')
            self.assertEqual(fields['fixed_file_version'], '1.2.3.4')
            self.assertEqual(fields['StringFileInfo/040904b0/ProductName'], 'Generic Installer')
            for o in result['observations']:
                self.assertEqual(base64.b64decode(o['raw_base64']), data[o['offset']:o['offset']+o['length']])

    def test_conflicting_language_values_survive_separately(self):
        result = version_observations(pe_image([version_blob(version='1.0'), version_blob(version='2.0')]))
        versions = [o for o in result['observations'] if o['field'].endswith('/ProductVersion')]
        self.assertEqual([v['value'] for v in versions], ['1.0', '2.0'])
        self.assertNotEqual(versions[0]['resource_path'], versions[1]['resource_path'])

    def test_noncanonical_strings_are_preserved_with_warning(self):
        result = version_observations(pe_image([version_blob(version='1.0\0XXXXX')]))
        version = next(o for o in result['observations'] if o['field'].endswith('/ProductVersion'))
        self.assertEqual(version['value'], '1.0\0XXXXX')
        self.assertEqual(version['warning'], 'embedded_nul_in_version_string')

    def test_arbitrary_embedded_version_text_is_not_a_version_resource(self):
        data = bytearray(pe_image()); struct.pack_into('<II', data, 264, 0, 0)
        self.assertEqual(version_observations(bytes(data))['status'], 'no_version_resource')
        self.assertEqual(inspect_bytes(b'PK\x03\x04ProductVersion 7.0', 'pe')['status'], 'unsupported_format')

    def test_bad_offsets_cycles_truncation_and_block_lengths_are_bounded(self):
        mutations = [lambda d: struct.pack_into('<I', d, 60, 0xffffffff),
                     lambda d: struct.pack_into('<I', d, 532, 0x80000000),
                     lambda d: struct.pack_into('<I', d, 264, 0x90000000),
                     lambda d: struct.pack_into('<H', d, 600, 0),
                     lambda d: d.__delitem__(slice(100, None))]
        for mutation in mutations:
            data = bytearray(pe_image()); mutation(data)
            self.assertEqual(inspect_bytes(bytes(data), 'pe')['status'], 'invalid_format')


class InspectionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name); self.source = self.root / 'source'; self.source.mkdir()
        self.cache = self.root / 'cache'

    def file(self, name, data):
        path = self.source / name; path.parent.mkdir(parents=True, exist_ok=True); path.write_bytes(data)
        return dict(path=name, sha256=hashlib.sha256(data).hexdigest(), size=len(data))

    def test_cache_is_reused_but_source_bytes_are_still_verified(self):
        item = self.file('Setup.exe', pe_image())
        first = inspect_file(self.source, item, self.cache)
        with patch('bootdisk_ingest.inspection.inspect_bytes', side_effect=AssertionError('decoded again')):
            self.assertEqual(inspect_file(self.source, item, self.cache), first)
        (self.source/'Setup.exe').write_bytes(b'changed')
        self.assertEqual(inspect_file(self.source, item, self.cache)['status'], 'hash_mismatch')
        (self.source/'Setup.exe').unlink()
        self.assertEqual(inspect_file(self.source, item, self.cache)['status'], 'missing_file')

    def test_encoding_assumption_and_raw_excerpt_are_retained(self):
        data = 'Prøveversjon\r\n'.encode('cp1252')
        result = inspect_bytes(data, 'text')['observations'][0]
        self.assertEqual(result['value'], 'Prøveversjon\r\n')
        self.assertTrue(result['encoding_assumed'])
        self.assertEqual(base64.b64decode(result['raw_base64']), data)
        utf16 = inspect_bytes(b'\xff\xfe' + 'Demo'.encode('utf-16le'), 'text')['observations'][0]
        self.assertFalse(utf16['encoding_assumed']); self.assertEqual(utf16['offset'], 2)

    def test_malformed_cache_and_manifest_fail_explicitly(self):
        item = self.file('Setup.exe', pe_image())
        inspect_file(self.source, item, self.cache)
        next(self.cache.glob('*.json')).write_text('[]')
        with self.assertRaises(ValueError):
            inspect_file(self.source, item, self.cache)
        manifest = self.root/'bad.json'; manifest.write_text('[]')
        with self.assertRaises(ValueError):
            inspect_manifest(manifest, self.source, self.cache)

    def test_unsafe_paths_symlinks_permissions_and_limits_are_explicit(self):
        item = self.file('readme.txt', b'text')
        self.assertEqual(inspect_file(self.source, dict(item, path='../readme.txt'), self.cache)['status'], 'unsafe_path')
        (self.source/'link.txt').symlink_to(self.source/'readme.txt')
        self.assertEqual(inspect_file(self.source, dict(item, path='link.txt'), self.cache)['status'], 'unsafe_path')
        with patch('pathlib.Path.open', side_effect=PermissionError()):
            self.assertEqual(inspect_file(self.source, item, self.cache)['status'], 'permission_denied')
        with patch('bootdisk_ingest.inspection.MAX_TEXT', 2):
            self.assertEqual(inspect_file(self.source, item, self.cache)['status'], 'size_limit')

    def test_manifest_routing_keeps_shared_launcher_and_adjacent_text_as_observations(self):
        first = self.file('A/Setup.exe', pe_image()); second = self.file('B/Setup.exe', pe_image())
        readme = self.file('A/readme.txt', b'Example trial edition')
        other = self.file('Other/license.txt', b'Not for these programs')
        manifest = dict(schema_version='kcd-director-experimental-1', file_inventory=[first,second,readme,other],
                        entries=[dict(source_id=key, normalized=dict(title=key), files=dict(inventory_refs=[f['path']]), issues=[])
                                 for key,f in [('K1D1',first),('K1D2',second)]])
        path = self.root/'manifest.json'; path.write_text(json.dumps(manifest))
        before = path.read_bytes()
        result = inspect_manifest(path, self.source, self.cache, nearby_text=True)
        self.assertEqual(len(result['entries']), 2); self.assertEqual(len(result['files']), 3)
        self.assertEqual(result['entries'][0]['files'][1]['association'], 'adjacent_text_hint')
        self.assertEqual(len(list(self.cache.glob('*.json'))), 2)
        self.assertEqual(result, inspect_manifest(path, self.source, self.cache, nearby_text=True))
        self.assertEqual(path.read_bytes(), before)
        self.assertNotIn('claims', result)
        with self.assertRaises(ValueError):
            inspect_manifest(path, self.source, self.source/'cache')
        with patch('bootdisk_ingest.inspection.MAX_TOTAL', 1):
            limited = inspect_manifest(path, self.source, self.root/'other-cache')
        self.assertEqual(limited['summary']['outcomes'], {'run_size_limit':2})
        with self.assertRaises(SystemExit):
            main([str(path), '--source', str(self.source), '--cache', str(self.cache), '--output', str(self.source/'out.json')])
        self.assertFalse((self.source/'out.json').exists())


if __name__ == '__main__':
    unittest.main()
