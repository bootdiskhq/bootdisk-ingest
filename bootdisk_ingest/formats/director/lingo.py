"""Structural D6 Lingo decoding, not a Lingo evaluator or full decompiler."""

from dataclasses import dataclass
from .binary import UnsupportedDirector, View


@dataclass(frozen=True)
class Constant:
    kind: int
    value: object
    raw: bytes


@dataclass(frozen=True)
class Instruction:
    offset: int  # Relative to the Lscr payload, not the handler.
    opcode: int
    operand: int | None
    size: int

    @property
    def operation(self):
        return (self.opcode & 0x3F) + 0x40 if self.opcode >= 0x40 else self.opcode


@dataclass(frozen=True)
class Handler:
    name: bytes
    offset: int
    code: bytes
    instructions: tuple[Instruction, ...]


@dataclass(frozen=True)
class LiteralCall:
    handler: bytes
    offset: int
    name: bytes
    arguments: tuple[object, ...]


@dataclass(frozen=True)
class Script:
    resource_id: int
    flags: int
    names: tuple[bytes, ...]
    constants: tuple[Constant, ...]
    handlers: tuple[Handler, ...]

    def literal_calls(self):
        """Observe contiguous literal-push / argument-count / call sequences.

        Unknown operations break the sequence. Calls with computed arguments
        remain in the bytecode but are not guessed here. Branches into a literal
        sequence invalidate it; existence never implies runtime reachability.
        """
        out = []
        for handler in self.handlers:
            instructions = handler.instructions
            targets = {
                i.offset + (-i.operand if i.operation == 0x54 else i.operand)
                for i in instructions
                if i.operation in (0x53, 0x54, 0x55)
            }
            for index, call in enumerate(instructions):
                if call.operation != 0x57 or index < 1:
                    continue
                count = instructions[index - 1]
                if count.operation not in (0x42, 0x43) or count.operand > index - 1:
                    continue
                pushes = instructions[index - 1 - count.operand : index - 1]
                sequence = (*pushes, count, call)
                if any(i.offset in targets for i in sequence[1:]):
                    continue
                args = []
                for push in pushes:
                    if push.operation == 0x03:
                        args.append(0)
                    elif push.operation == 0x41:
                        bits = (push.size - 1) * 8
                        value = push.operand
                        args.append(value - (1 << bits) if value & (1 << (bits - 1)) else value)
                    elif push.operation == 0x44:
                        c = self.constants[push.operand // 8]
                        if c.kind not in (1, 4):
                            break
                        args.append(c.value)
                    else:
                        break
                else:
                    out.append(
                        LiteralCall(
                            handler.name, call.offset, self.names[call.operand], tuple(args)
                        )
                    )
        return tuple(out)


@dataclass(frozen=True)
class ContextEntry:
    index: int  # Lctx index, 1-based; Lscr's embedded script ID may be stale.
    resource_id: int
    unused: bool
    flags: int
    next_unused: int


@dataclass(frozen=True)
class Context:
    resource_id: int
    names_id: int
    entries: tuple[ContextEntry, ...]


def read_names(archive, resource_id):
    v = archive.view(resource_id, "Lnam")
    offset, count = v.u16(16), v.u16(18)
    v.require(offset >= 20, 16, "name table overlaps header")
    out = []
    for _ in range(count):
        name = v.pascal(offset)
        offset += len(name) + 1
        out.append(name)
    return tuple(out)


def read_context(archive, resource_id):
    v = archive.view(resource_id, "Lctx")
    count, offset, stride = v.u32(8), v.u16(16), v.u16(18)
    v.require(stride == 12 and offset >= 42 and v.u32(12) == count, 8, "invalid Lctx dimensions")
    raw = [(v.i32(p + 4), v.u16(p + 8), v.i16(p + 10)) for p in v.table(offset, count, stride)]
    unused = set()
    next_unused = v.i16(40)
    while next_unused != -1:
        v.require(
            0 <= next_unused < count and next_unused not in unused,
            40,
            "invalid/cyclic Lctx free list",
        )
        unused.add(next_unused)
        next_unused = raw[next_unused][2]
    entries = []
    for i, (rid, flags, nxt) in enumerate(raw):
        if rid != -1:
            archive.resource(rid, "Lscr")
        entries.append(ContextEntry(i + 1, rid, i in unused, flags, nxt))
    names_id = v.u32(32)
    archive.resource(names_id, "Lnam")
    return Context(resource_id, names_id, tuple(entries))


def decode_instructions(code, base=0):
    v = View(code, "Lscr code")
    instructions = []
    p = 0
    while p < len(code):
        op = code[p]
        if op >= 0xC0:
            raise UnsupportedDirector(
                "Four-byte operand opcodes are not qualified for this D6 profile"
            )
        width = 0 if op < 0x40 else 1 if op < 0x80 else 2 if op < 0xC0 else 4
        operand = int.from_bytes(v.span(p + 1, width), "big") if width else None
        instructions.append(Instruction(base + p, op, operand, 1 + width))
        p += 1 + width
    return tuple(instructions)


def read_script(archive, resource_id, names):
    v = archive.view(resource_id, "Lscr")
    v.span(0, 92)
    v.require(v.u32(8) == len(v.data) and v.u32(12) == len(v.data), 8, "Lscr length mismatch")
    code_start = v.u16(16)
    v.require(92 <= code_start <= len(v.data), 16, "invalid code start")
    count, offset, store_size, store_offset = v.u16(78), v.u32(80), v.u32(84), v.u32(88)
    store = View(v.span(store_offset, store_size), f"Lscr[{resource_id}] constants")
    constants = []
    for p in v.table(offset, count, 8):
        kind, value = v.u32(p), v.u32(p + 4)
        raw = v.span(p, 8)
        if kind in (1, 9):
            raw = store.span(value + 4, store.u32(value))
            value = raw.split(b"\0", 1)[0] if kind == 1 else raw
        elif kind == 4:
            value = v.i32(p + 4)
        constants.append(Constant(kind, value, raw))
    # Retain property/global references and reject dangling name indices.
    for count_at, offset_at in ((60, 62), (66, 68)):
        for p in v.table(v.u32(offset_at), v.u16(count_at), 2):
            v.require(v.u16(p) < len(names), p, "invalid property/global name")
    handlers = []
    for p in v.table(v.u32(74), v.u16(72), 42):
        ni, length, start = v.u16(p), v.u32(p + 4), v.u32(p + 8)
        v.require(ni < len(names) and start >= code_start, p, "invalid handler reference")
        code = v.span(start, length)
        for count_at, offset_at in ((12, 14), (18, 20)):
            for q in v.table(v.u32(p + offset_at), v.u16(p + count_at), 2):
                v.require(v.u16(q) < len(names), q, "invalid argument/local name")
        instructions = decode_instructions(code, start)
        boundaries = {i.offset for i in instructions} | {start + length}
        for i in instructions:
            op, arg = i.operation, i.operand
            if op == 0x44:
                v.require(
                    arg % 8 == 0 and arg // 8 < len(constants),
                    i.offset,
                    "invalid constant reference",
                )
            if op in (
                0x45,
                0x46,
                0x48,
                0x49,
                0x4A,
                0x4E,
                0x4F,
                0x50,
                0x57,
                0x5F,
                0x60,
                0x61,
                0x62,
                0x63,
                0x66,
                0x67,
            ):
                v.require(arg < len(names), i.offset, "invalid instruction name reference")
            if op in (0x53, 0x54, 0x55):
                target = i.offset + (-arg if op == 0x54 else arg)
                v.require(
                    target in boundaries,
                    i.offset,
                    "branch target is not a handler instruction boundary",
                )
        handlers.append(Handler(names[ni], start, code, instructions))
    return Script(resource_id, v.u32(38), tuple(names), tuple(constants), tuple(handlers))
