"""Small synthetic format fixtures; no original software is redistributed."""

import struct


def put(data, offset, fmt, value, endian=">"):
    struct.pack_into(endian + fmt, data, offset, value)


def archive(chunks, endian="<"):
    """Allocate resource IDs independently of real-media layout."""

    def tag(value):
        raw = value.encode("ascii")
        return raw[::-1] if endian == "<" else raw

    count = len(chunks) + 3
    map_size = 24 + count * 20
    offset = 44 + 8 + map_size
    rows = [("RIFX", 0, 0), ("imap", 24, 12), ("mmap", map_size, 44)]
    tail = bytearray()
    for kind, raw in chunks:
        rows.append((kind, len(raw), offset + len(tail)))
        tail += tag(kind) + struct.pack(endian + "I", len(raw)) + raw
        if len(raw) % 2:
            tail += b"\0"
    result = bytearray(offset) + tail
    rows[0] = ("RIFX", len(result) - 8, 0)
    result[0:4] = tag("RIFX")
    put(result, 4, "I", len(result) - 8, endian)
    result[8:12] = tag("MC95")
    result[12:16] = tag("imap")
    put(result, 16, "I", 24, endian)
    put(result, 20, "I", 1, endian)
    put(result, 24, "I", 44, endian)
    put(result, 28, "I", 0x4C7, endian)
    result[44:48] = tag("mmap")
    put(result, 48, "I", map_size, endian)
    for o, fmt, v in [(52, "H", 24), (54, "H", 20), (56, "I", count), (60, "I", count)]:
        put(result, o, fmt, v, endian)
    for i, (kind, size, off) in enumerate(rows):
        p = 76 + i * 20
        result[p : p + 4] = tag(kind)
        put(result, p + 4, "I", size, endian)
        put(result, p + 8, "I", off, endian)
    return bytes(result)


def names(values):
    b = bytearray(20)
    put(b, 16, "H", 20)
    put(b, 18, "H", len(values))
    for v in values:
        b += bytes([len(v)]) + v
    put(b, 8, "I", len(b))
    put(b, 12, "I", len(b))
    return bytes(b)


def context(rows, names_id=3, first_unused=-1):
    b = bytearray(96 + len(rows) * 12)
    for o, fmt, v in [
        (8, "I", len(rows)),
        (12, "I", len(rows)),
        (16, "H", 96),
        (18, "H", 12),
        (32, "I", names_id),
        (40, "h", first_unused),
    ]:
        put(b, o, fmt, v)
    for i, (rid, nxt) in enumerate(rows):
        put(b, 100 + i * 12, "i", rid)
        put(b, 106 + i * 12, "h", nxt)
    return bytes(b)


def script(code=b"\x44\x00\x42\x01\x57\x01\x01", literal=b"tools\\setup.exe"):
    b = bytearray(92) + code
    table = len(b)
    b += bytearray(42)
    put(b, table, "H", 0)
    put(b, table + 4, "I", len(code))
    put(b, table + 8, "I", 92)
    const_table = len(b)
    b += struct.pack(">II", 1, 0)
    store = len(b)
    b += struct.pack(">I", len(literal) + 1) + literal + b"\0"
    for o, fmt, v in [
        (8, "I", len(b)),
        (12, "I", len(b)),
        (16, "H", 92),
        (72, "H", 1),
        (74, "I", table),
        (78, "H", 1),
        (80, "I", const_table),
        (84, "I", len(b) - store),
        (88, "I", store),
    ]:
        put(b, o, fmt, v)
    return bytes(b)


def score(deltas=None):
    if deltas is None:
        sprite = bytearray(24)
        sprite[0] = 1
        put(sprite, 4, "H", 3)
        put(sprite, 6, "H", 77)
        deltas = [[(144, bytes(sprite))], [(150, b"\x00\x4e")]]
    frames = bytearray()
    for changes in deltas:
        payload = b"".join(struct.pack(">HH", len(raw), off) + raw for off, raw in changes)
        frames += struct.pack(">H", len(payload) + 2) + payload
    stream = struct.pack(">IIIHHHH", 20 + len(frames), 20, 0, 11, 24, 126, 0) + frames
    b = bytearray(32) + stream
    for o, fmt, v in [
        (0, "I", len(b)),
        (4, "i", -3),
        (8, "I", 12),
        (12, "I", 2),
        (16, "I", 2),
        (20, "I", len(stream)),
        (24, "I", 0),
        (28, "I", len(stream)),
    ]:
        put(b, o, fmt, v)
    return bytes(b)


def library_list(name=b"Generic", path=b"", first=1, last=1, parent=1024):
    fields = [
        b"",
        bytes([len(name)]) + name,
        bytes([len(path)]) + path,
        b"\0\0",
        struct.pack(">HHI", first, last, parent),
    ]
    starts = []
    raw = b""
    for field in fields:
        starts.append(len(raw))
        raw += field
    b = struct.pack(">IHHHH", 12, 0, 1, 4, 0) + struct.pack(">H", len(starts))
    return b + b"".join(struct.pack(">I", p) for p in starts) + struct.pack(">I", len(raw)) + raw


def linked_archive(path=b"", parent=1024):
    # IDs: MCsL=3, CAS*=4, CASt=5, KEY*=6, RTE1=7. First member deliberately isn't 1.
    key = struct.pack("<HHII", 12, 12, 2, 2)
    key += struct.pack("<II", 4, parent) + b"*SAC" + struct.pack("<II", 7, 5) + b"1ETR"
    return archive(
        [
            ("MCsL", library_list(path=path, first=10, last=10, parent=parent)),
            ("CAS*", struct.pack(">I", 5)),
            ("CASt", struct.pack(">III", 12, 0, 0)),
            ("KEY*", key),
            ("RTE1", b"Generic title"),
        ]
    )
