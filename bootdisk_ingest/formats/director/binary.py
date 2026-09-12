"""Checked, resource-relative binary reads. No external paths are followed."""

import struct


class DirectorError(ValueError):
    """Malformed or inconsistent data, with a resource-relative location."""


class UnsupportedDirector(DirectorError):
    """A format variant outside the deliberately narrow supported profile."""


class View:
    def __init__(self, data: bytes, label: str, endian: str = ">"):
        self.data = data
        self.label = label
        self.endian = endian

    def require(self, condition, offset, reason):
        if not condition:
            raise DirectorError(f"{self.label}+0x{offset:x}: {reason}")

    def span(self, offset, size):
        self.require(
            0 <= offset <= len(self.data) and 0 <= size <= len(self.data) - offset,
            offset,
            f"span of {size} bytes exceeds {len(self.data)} bytes",
        )
        return self.data[offset : offset + size]

    def number(self, offset, fmt):
        size = struct.calcsize(fmt)
        return struct.unpack(self.endian + fmt, self.span(offset, size))[0]

    def u16(self, offset):
        return self.number(offset, "H")

    def i16(self, offset):
        return self.number(offset, "h")

    def u32(self, offset):
        return self.number(offset, "I")

    def i32(self, offset):
        return self.number(offset, "i")

    def table(self, offset, count, stride):
        self.span(offset, count * stride)
        return range(offset, offset + count * stride, stride)

    def pascal(self, offset=0):
        size = self.span(offset, 1)[0]
        return self.span(offset + 1, size)
