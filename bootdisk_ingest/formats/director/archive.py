"""Uncompressed Director 6 resource maps and cast relationships.

Original payloads and identifiers remain available even for unparsed tags.
KEY parent IDs are logical IDs, not necessarily resource IDs. MCsL paths
are historical observations only; opening another file requires caller action.
"""

from dataclasses import dataclass
from pathlib import Path
from .binary import DirectorError, UnsupportedDirector, View


@dataclass(frozen=True)
class Resource:
    id: int
    tag: str
    size: int
    offset: int
    flags: int


@dataclass(frozen=True)
class Key:
    child: int
    parent: int
    tag: str


@dataclass(frozen=True)
class CastLibrary:
    id: int
    name: bytes
    path: bytes
    first_member: int
    last_member: int
    resource_id: int


@dataclass(frozen=True)
class CastMember:
    table_id: int
    slot: int
    resource_id: int
    kind: int
    script_id: int
    info: tuple[bytes, ...]
    data: bytes

    @property
    def name(self):
        return (
            View(self.info[1], "cast name").pascal() if len(self.info) > 1 and self.info[1] else b""
        )


class Archive:
    """Read the 0x04c7/MC95 profile; other versions fail explicitly.

    Accepting bytes makes synthetic tests possible without preserved media.
    Use open() for bounded reads from a caller-selected file.
    """

    MAX_FILE_SIZE = 128 * 1024 * 1024
    MAX_RESOURCES = 250_000

    def __init__(self, data: bytes):
        if len(data) > self.MAX_FILE_SIZE:
            raise DirectorError("Director file exceeds 128 MiB reader limit")
        self.data = bytes(data)
        marker = data[:4]
        if marker not in (b"XFIR", b"RIFX"):
            raise UnsupportedDirector("Expected an uncompressed XFIR/RIFX Director archive")
        self.endian = "<" if marker == b"XFIR" else ">"
        v = View(self.data, "archive", self.endian)
        self._v = v
        v.require(v.u32(4) + 8 == len(data), 4, "declared container length differs from file")
        if self.tag(8) not in ("MC95", "MV93"):
            raise UnsupportedDirector("Only uncompressed MC95/MV93 forms is supported")
        v.require(self.tag(12) == "imap", 12, "missing imap")
        v.require(v.u32(16) >= 12, 16, "short imap")
        v.span(20, v.u32(16))
        self.version = v.u32(28)
        if self.version != 0x04C7:
            raise UnsupportedDirector(f"Unqualified Director version 0x{self.version:x}")
        mmap = v.u32(24)
        v.require(self.tag(mmap) == "mmap", mmap, "imap does not point to mmap")
        m = View(v.span(mmap + 8, v.u32(mmap + 4)), "mmap", self.endian)
        header, stride, capacity, count = m.u16(0), m.u16(2), m.u32(4), m.u32(8)
        m.require(header >= 24 and stride >= 20 and count <= capacity, 0, "invalid map dimensions")
        m.require(count <= self.MAX_RESOURCES, 8, "resource count exceeds reader limit")
        m.table(header, capacity, stride)
        resources = []
        for i, p in enumerate(m.table(header, count, stride)):
            raw = m.span(p, 4)
            tag = (raw[::-1] if self.endian == "<" else raw).decode("latin1")
            r = Resource(i, tag, m.u32(p + 4), m.u32(p + 8), m.u16(p + 12))
            if tag not in ("free", "junk"):
                v.span(r.offset, r.size + 8)
                v.require(
                    self.tag(r.offset) == tag and v.u32(r.offset + 4) == r.size,
                    r.offset,
                    f"resource {i} header disagrees with mmap",
                )
            resources.append(r)
        self.resources = tuple(resources)

    @classmethod
    def open(cls, path):
        with Path(path).open("rb") as source:
            return cls(source.read(cls.MAX_FILE_SIZE + 1))

    def tag(self, offset):
        raw = self._v.span(offset, 4)
        return (raw[::-1] if self.endian == "<" else raw).decode("latin1")

    def ids(self, tag):
        return tuple(r.id for r in self.resources if r.tag == tag)

    def resource(self, resource_id, expected=None):
        if not 0 <= resource_id < len(self.resources):
            raise DirectorError(f"Invalid resource reference {resource_id}")
        r = self.resources[resource_id]
        if r.tag in ("free", "junk") or (expected is not None and r.tag != expected):
            raise DirectorError(
                f"Resource {resource_id}: expected {expected or 'live resource'}, got {r.tag}"
            )
        return r

    def payload(self, resource_id, expected=None):
        r = self.resource(resource_id, expected)
        return self._v.span(r.offset + 8, r.size)

    def view(self, resource_id, expected=None):
        r = self.resource(resource_id, expected)
        return View(self.payload(resource_id), f"{r.tag}[{r.id}]")

    def keys(self):
        result = []
        for rid in self.ids("KEY*"):
            v = View(self.payload(rid), f"KEY*[{rid}]", self.endian)
            stride, capacity, count = v.u16(0), v.u32(4), v.u32(8)
            v.require(
                stride == 12 and v.u16(2) == 12 and count <= capacity,
                0,
                "invalid key table dimensions",
            )
            v.table(12, capacity, stride)
            for p in v.table(12, count, stride):
                raw = v.span(p + 8, 4)
                tag = (raw[::-1] if self.endian == "<" else raw).decode("latin1")
                self.resource(v.u32(p), tag)
                result.append(Key(v.u32(p), v.u32(p + 4), tag))
        return tuple(result)

    def libraries(self):
        result = []
        if len(self.ids("MCsL")) > 1:
            raise UnsupportedDirector("Multiple MCsL resources are not qualified")
        for rid in self.ids("MCsL"):
            v = self.view(rid)
            offset, count, stride = v.u32(0), v.u16(6), v.u16(8)
            if stride != 4:
                raise UnsupportedDirector("MCsL requires the four-field D6 layout")
            n = v.u16(offset)
            offsets = [v.u32(p) for p in v.table(offset + 2, n, 4)]
            size_pos = offset + 2 + n * 4
            size = v.u32(size_pos)
            raw = v.span(size_pos + 4, size)
            v.require(n == count * stride + 1, offset, "MCsL field count mismatch")
            offsets.append(size)
            v.require(
                all(0 <= a <= b <= size for a, b in zip(offsets, offsets[1:])),
                offset,
                "invalid MCsL field offsets",
            )
            fields = [raw[a:b] for a, b in zip(offsets, offsets[1:])]
            for i in range(count):
                p = i * stride
                bounds = View(fields[p + 4], f"MCsL[{rid}] library {i + 1}")
                result.append(
                    CastLibrary(
                        i + 1,
                        View(fields[p + 1], "library name").pascal(),
                        View(fields[p + 2], "library path").pascal() if fields[p + 2] else b"",
                        bounds.u16(0),
                        bounds.u16(2),
                        bounds.u32(4),
                    )
                )
        return tuple(result)

    def members(self, table_id):
        """Return physical CAS* slots; number them only with explicit cast bounds."""
        v = self.view(table_id, "CAS*")
        v.require(len(v.data) % 4 == 0, 0, "partial CAS* slot")
        out = []
        for slot, p in enumerate(v.table(0, len(v.data) // 4, 4)):
            rid = v.u32(p)
            if rid == 0:
                continue
            c = self.view(rid, "CASt")
            kind, info_size, data_size = c.u32(0), c.u32(4), c.u32(8)
            info_view = View(c.span(12, info_size), f"CASt[{rid}] info")
            data = c.span(12 + info_size, data_size)
            script, info = 0, ()
            if info_size:
                offset, script = info_view.u32(0), info_view.u32(16)
                n = info_view.u16(offset)
                starts = [info_view.u32(q) for q in info_view.table(offset + 2, n + 1, 4)]
                base = offset + 2 + 4 * (n + 1)
                info_view.require(
                    starts[0] == 0 and all(a <= b for a, b in zip(starts, starts[1:])),
                    offset,
                    "invalid cast info offsets",
                )
                info = tuple(info_view.span(base + a, b - a) for a, b in zip(starts, starts[1:]))
            out.append(CastMember(table_id, slot, rid, kind, script, info, data))
        return tuple(out)

    def text(self, member):
        """Return (resource ID, raw RTE1 bytes) links, not inferred titles."""
        return tuple(
            (k.child, self.payload(k.child, "RTE1"))
            for k in self.keys()
            if k.parent == member.resource_id and k.tag == "RTE1"
        )

    def standalone_bounds(self):
        ids = self.ids("DRCF")
        if len(ids) != 1:
            raise DirectorError("Expected one DRCF for standalone cast bounds")
        v = self.view(ids[0])
        return v.u16(12), v.u16(14)
