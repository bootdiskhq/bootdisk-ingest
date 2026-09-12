"""D6 score deltas. Frames are sequential state observations, not UI reachability."""

from dataclasses import dataclass
from .binary import UnsupportedDirector, View


@dataclass(frozen=True)
class Label:
    frame: int
    raw: bytes

    @property
    def name(self):
        return self.raw.split(b"\r", 1)[0]


@dataclass(frozen=True)
class Sprite:
    channel: int
    kind: int
    cast_library: int
    cast_member: int
    detail_index: int
    raw: bytes


@dataclass(frozen=True)
class Frame:
    number: int
    offset: int
    main_channels: bytes
    sprites: tuple[Sprite, ...]


def read_labels(archive, resource_id):
    v = archive.view(resource_id, "VWLB")
    count = v.u16(0)
    positions = [(v.u16(p), v.u16(p + 2)) for p in v.table(2, count + 1, 4)]
    base = 2 + (count + 1) * 4
    out = []
    for (frame, start), (_, end) in zip(positions, positions[1:]):
        v.require(start <= end, base + start, "descending label offsets")
        out.append(Label(frame, v.span(base + start, end - start)))
    return tuple(out)


class Score:
    def __init__(self, archive, resource_id):
        self.resource_id = resource_id
        self.v = v = archive.view(resource_id, "VWSC")
        v.require(v.u32(0) == len(v.data), 0, "VWSC length mismatch")
        if v.i32(4) != -3:
            raise UnsupportedDirector("Only D6 score list version -3 is supported")
        p = v.u32(8)
        count, capacity, data_size = v.u32(p), v.u32(p + 4), v.u32(p + 8)
        v.require(2 <= count <= min(capacity, 1_000_000), p, "invalid score list count")
        v.table(p + 12, capacity, 4)
        base = p + 12 + capacity * 4
        v.span(base, data_size)
        offsets = [v.u32(q) for q in v.table(p + 12, count, 4)]
        v.require(
            all(0 <= a <= b <= data_size for a, b in zip(offsets, offsets[1:])),
            p,
            "invalid score list offsets",
        )
        self.offsets = tuple(base + o for o in offsets) + (base + data_size,)
        start = self.offsets[0]
        size = v.u32(start)
        self.start = start + v.u32(start + 4)
        self.end = start + size
        v.require(
            self.start >= start + 20 and self.start <= self.end <= self.offsets[1],
            start,
            "frame stream exceeds its detail-list block",
        )
        version, stride, channels = v.u16(start + 12), v.u16(start + 14), v.u16(start + 16)
        if (version, stride, channels) != (11, 24, 126):
            raise UnsupportedDirector(f"Unqualified score layout {(version, stride, channels)}")

    def detail(self, index):
        self.v.require(0 <= index < len(self.offsets) - 1, 0, "invalid sprite detail reference")
        start, end = self.offsets[index : index + 2]
        return self.v.span(start, end - start)

    def frames(self):
        v = self.v
        state = bytearray(144 + 120 * 24)
        p, number = self.start, 0
        while p < self.end:
            frame_offset = p
            v.require(p + 2 <= self.end, p, "partial frame header")
            length = v.u16(p)
            v.require(length >= 2 and p + length <= self.end, p, "invalid frame size")
            end = p + length
            p += 2
            while p < end:
                v.require(p + 4 <= end, p, "partial channel header")
                size, offset = v.u16(p), v.u16(p + 2)
                p += 4
                v.require(
                    size > 0 and p + size <= end and offset + size <= len(state),
                    p,
                    "channel delta exceeds frame/state",
                )
                state[offset : offset + size] = v.span(p, size)
                p += size
            number += 1
            v.require(number <= 100_000, p, "frame count exceeds reader limit")
            sprites = []
            for channel in range(120):
                raw = bytes(state[144 + channel * 24 : 144 + (channel + 1) * 24])
                s = View(raw, f"frame {number} channel {channel + 1}")
                sprites.append(Sprite(channel + 1, raw[0], s.u16(4), s.u16(6), s.u32(8), raw))
            yield Frame(number, frame_offset, bytes(state[:144]), tuple(sprites))
