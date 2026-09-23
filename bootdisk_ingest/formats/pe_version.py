"""Bounded PE VERSIONINFO observations; never load or execute a Windows image."""
import base64
import struct


class PEError(ValueError):
    pass


def version_observations(data):
    """Return every selected VERSIONINFO language, retaining byte locations.

    Product/FileVersion may describe an installer runtime. These are observations
    about this file, never a decision about the software it installs.
    """
    def region(offset, size):
        if offset < 0 or size < 0 or offset + size > len(data):
            raise PEError("out-of-bounds PE data")
        return data[offset:offset + size]

    def unpack(fmt, offset):
        return struct.unpack(fmt, region(offset, struct.calcsize(fmt)))

    if data[:2] != b"MZ":
        return {"status": "unsupported_format", "observations": []}
    pe, = unpack("<I", 60)
    if region(pe, 4) != b"PE\0\0":
        return {"status": "unsupported_format", "observations": []}
    count, = unpack("<H", pe + 6)
    optional_size, = unpack("<H", pe + 20)
    optional = pe + 24
    region(optional, optional_size)
    magic, = unpack("<H", optional)
    if magic not in (0x10b, 0x20b):
        return {"status": "unsupported_format", "observations": []}
    directory_offset = 96 if magic == 0x10b else 112
    if optional_size < directory_offset:
        raise PEError("short optional header")
    directory_count, = unpack("<I", optional + directory_offset - 4)
    if directory_count < 3:
        return {"status": "no_version_resource", "observations": []}
    if optional_size < directory_offset + 24 or not 1 <= count <= 96:
        raise PEError("invalid section/resource header")
    resource_rva, resource_size = unpack("<II", optional + directory_offset + 16)
    if resource_rva == 0 and resource_size == 0:
        return {"status": "no_version_resource", "observations": []}
    sections = []
    for index in range(count):
        header = optional + optional_size + index * 40
        region(header, 40)
        _, address, size, pointer = unpack("<IIII", header + 8)
        sections.append((address, size, pointer))

    def map_rva(rva, size):
        matches = [pointer + rva - address for address, length, pointer in sections
                   if address <= rva and rva + size <= address + length]
        if len(matches) != 1:
            raise PEError("unmapped or ambiguous resource RVA")
        region(matches[0], size)
        return matches[0]

    if not 16 <= resource_size <= 8 * 1024 * 1024:
        raise PEError("resource size outside supported bounds")
    base = map_rva(resource_rva, resource_size)

    def resource(offset, size):
        if offset < 0 or offset + size > resource_size:
            raise PEError("resource directory escapes its bounds")
        return region(base + offset, size)

    observations = []
    leaves = 0
    visited = set()

    def parse_version(offset, size, resource_path):
        if not 6 <= size <= 1024 * 1024:
            raise PEError("version resource size outside supported bounds")
        end = offset + size
        region(offset, size)
        blocks = 0

        def emit(field, value, start, length):
            observations.append(dict(field=field, value=value, offset=start, length=length,
                                     resource_path=resource_path,
                                     raw_base64=base64.b64encode(region(start, length)).decode("ascii")))

        def block(start, parent_end, keys):
            nonlocal blocks
            blocks += 1
            if blocks > 512 or len(keys) > 3 or start + 6 > parent_end:
                raise PEError("invalid/deep version block")
            length, value_length, kind = unpack("<HHH", start)
            finish = start + length
            if length < 8 or finish > parent_end or kind not in (0, 1):
                raise PEError("invalid version block length/type")
            cursor = start + 6
            key_start = cursor
            while cursor + 2 <= finish and region(cursor, 2) != b"\0\0":
                cursor += 2
            if cursor + 2 > finish:
                raise PEError("unterminated version key")
            key = region(key_start, cursor - key_start).decode("utf-16le")
            path = keys + [key]
            value_start = (cursor + 2 + 3) & ~3
            value_size = value_length * (2 if kind else 1)
            if value_start + value_size > finish and value_size:
                raise PEError("version value escapes block")
            if not keys:
                if key != "VS_VERSION_INFO" or kind != 0:
                    raise PEError("invalid version root")
                if value_size:
                    if value_size != 52 or unpack("<I", value_start)[0] != 0xfeef04bd:
                        raise PEError("invalid fixed version info")
                    for name, delta in (("fixed_file_version", 8), ("fixed_product_version", 16)):
                        high, low = unpack("<II", value_start + delta)
                        emit(name, ".".join(map(str, (high >> 16, high & 65535, low >> 16, low & 65535))), value_start + delta, 8)
            if len(path) == 4 and path[1] == "StringFileInfo":
                if kind != 1:
                    raise PEError("non-text version string")
                text = region(value_start, value_size).decode("utf-16le").rstrip("\0")
                emit("/".join(path[1:]), text, value_start, value_size)
                if "\0" in text:
                    observations[-1]["warning"] = "embedded_nul_in_version_string"
            cursor = (value_start + value_size + 3) & ~3
            while cursor < finish:
                if not any(region(cursor, finish - cursor)):
                    break
                child_end = block(cursor, finish, path)
                cursor = (child_end + 3) & ~3
            return finish

        block(offset, end, [])

    def directory(relative, path):
        nonlocal leaves
        if relative in visited or len(path) > 2:
            raise PEError("cyclic/deep resource directory")
        visited.add(relative)
        header = resource(relative, 16)
        named, numbered = struct.unpack_from("<HH", header, 12)
        if named + numbered > 256:
            raise PEError("too many resource entries")
        table = resource(relative + 16, (named + numbered) * 8)
        for index in range(named + numbered):
            name, target = struct.unpack_from("<II", table, index * 8)
            if not path and name != 16:
                continue
            if name & 0x80000000:
                string_offset = name & 0x7fffffff
                length, = struct.unpack("<H", resource(string_offset, 2))
                if length > 256:
                    raise PEError("long resource name")
                name = resource(string_offset + 2, length * 2).decode("utf-16le")
            next_path = path + [name]
            if target & 0x80000000:
                directory(target & 0x7fffffff, next_path)
            else:
                if len(next_path) != 3:
                    raise PEError("unexpected version resource hierarchy")
                leaves += 1
                if leaves > 32:
                    raise PEError("too many version resources")
                rva, size, _, _ = struct.unpack("<IIII", resource(target, 16))
                parse_version(map_rva(rva, size), size, next_path)

    try:
        directory(0, [])
    except UnicodeError as exc:
        raise PEError("invalid UTF-16 version text") from exc
    return {"status": "observed" if leaves else "no_version_resource", "observations": observations}
