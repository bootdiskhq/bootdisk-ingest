# Experimental Director 6 reader

This is a read-only **format layer**, not a K-CD adapter, player, full Lingo
Decompiler, or automatic replacement for missing K.DTX. Existing ingest commands
and their manifest contract are unchanged.

## Qualified profile

The reader accepts uncompressed `XFIR` / `RIFX`, `MC95` cast or `MV93` movie forms,
and imap version field `0x04c7`. The score profile is list version -3, frame
version 11, 144 main-channel bytes and 120 24-byte sprite channels. Unsupported
variants raise `UnsupportedDirector`; corrupt structures raise `DirectorError`
(a `ValueError`) with a resource-relative location where available.

Both supplied K-CD 1/2000 originals were tested. Big-endian containers are
covered with synthetic fixtures, not a second original source. This is deliberately
narrow qualification, not a claim to support every Director 6 file.

## API

```python
from bootdisk_ingest.formats.director import Archive, Score
from bootdisk_ingest.formats.director.links import CastLinks

movie = Archive.open("K-CN.dxr")
constant = Archive.open("Constant.cxt")
# Library IDs come from movie.libraries(), not filenames or publication rules.
links = CastLinks(movie, {3: constant})
for frame in Score(movie, movie.ids("VWSC")[0]).frames():
    for sprite in frame.sprites:
        if not sprite.kind or not sprite.cast_member:
            continue
        link = links.resolve(sprite)
        if link and link.script:
            for call in link.script.literal_calls():
                print(frame.number, sprite.channel, call.name, call.arguments)
```

`Archive` exposes resources, checked original payloads, KEY relationships, MCsL
libraries, CAS* slots / CASt members and raw linked RTE1 text. A CAS* slot is
zero-based; `CastLinks` applies the declared first member from MCsL. Logical KEY
parent IDs are never assumed to be mmap resource IDs. External casts are supplied
explicitly and checked against the declared member bounds. This checks structural
compatibility, not authenticity; callers retain responsibility for choosing the
right cast. Historical external paths are never opened.

`read_context`, `read_names`, and `read_script` expose the Lctx free-list state,
original names, constants, handler bytecode and instruction references. The Lctx
index is authoritative for links; the potentially stale embedded Lscr script ID
is not substituted. Unused nonempty context entries remain available as evidence.
No classification of cast contents as current software is made.

`Score.frames()` yields immutable sequential snapshots, including inactive sprite
records and the raw main-channel state. Frame deltas, list offsets and stream
boundaries are checked. `Score.detail()` returns original detail-list bytes;
sprite behaviors and their initializer data are **not yet semantically decoded**.
`read_labels` preserves duplicates and original label/comment bytes.

### Literal-call observations

A `LiteralCall` means an actual call instruction immediately follows a supported
sequence of literal pushes and an argument count. It is stronger than a string
search. It is **not proof that the call executes**, or that the surrounding page is
reachable from a menu. Calls with computed arguments are omitted from this
convenience view but retained in the original instructions. Branches entering
partway through the sequence prevent a literal-call observation.

Recognized values are string/integer constants and immediate integer pushes.
Floating-point and unknown constants remain raw. Unknown instructions are retained
where the operand framing is qualified; opcodes with four-byte operands are
explicitly unqualified. No function, filename, Chicken label or program name is
special-cased in production code. A later adapter must decide how to interpret
navigation, current-directory state, active entries and conflicting launch paths.

## Observation command

```sh
python -m bootdisk_ingest.formats.director K-CN.dxr \
  --cast 3=Constant.cxt > director-observations.json
```

Output is an experimental JSON projection to stdout. Errors go to stderr with
status 2, before any JSON is emitted. Keep redirected output outside preserved
source directories. `--cast` is repeatable, with distinct IDs. The projection
contains source hashes, script constants and literal calls, library metadata,
labels and references/calls/texts at labeled frames. It does not claim UI
reachability. Missing external casts are reported as unresolved library IDs.
Bytes are represented by `hex` plus a reversible `latin1_view`; the latter is a
byte view, **not a claim about the source's character encoding**. Original bytecode
and arbitrary resources remain available through the API and preserved originals;
the projection is not a full substitute for those originals.

Limits: 128 MiB per archive, 250,000 mmap entries, 1,000,000 score detail entries,
and 100,000 frames. These bound work on hostile/corrupt headers; they are reader
limits, not Director format limits. There is no decompression, file execution,
network access, filesystem discovery, launch-path normalization, or media hashing
beyond explicitly supplied input bytes in this layer.

## Tests

Standard suite (no historical binaries required):

```sh
python -m unittest discover -s tests -v
```

Original-byte regressions:

```sh
BOOTDISK_DIRECTOR_FIXTURES=/path/to/original-files \
  python -m unittest discover -s tests -v
```

That directory must contain `Constant.cxt` and `K-CN.dxr`. An explicitly configured
missing/wrong fixture fails rather than silently skipping. SHA-256 values:

- Constant.cxt: `ca69e7af983bbeb1bd87a954ea25a90f12458148d0f373cfc0876f7f09f121c5`
- K-CN.dxr: `ae4a51fc45f97c1f6a7195e13cee8c1287849d6ac6d326a61c1710789e14f82c`

Original regressions check 229 Constant scripts, 88 movie scripts, 446 Constant
members, 624 labels, all 1,163 score frames, the four WinAmp/Half-Life/Prince3D/Unreal
chains and the four contradictory NHL direct-call targets. Expected page and
member numbers live **only in source-specific regression tests**. The reader
neither silently repairs those conflicts nor imports NHL as an entry. It does not
verify executable occurrence or installation results; that belongs to inventory
and adapter work. Original binaries are not included in the source distribution.

Synthetic tests cover endian separation, raw unknown resources, logical parent
IDs, non-default member numbering, missing external casts, invalid pointers,
cyclic free lists, partial operands, bad branches, computed versus literal calls,
delta inheritance, duplicate labels and malformed input handling.

## Remaining qualification

Read another old K-CD without K.DTX before widening the profile. Extend deliberately
when new structural evidence warrants it. A complete adapter still needs active
menu reachability, behaviors/dynamic script effects, language casts where relevant,
editorial grouping, inventory resolution and conflict policy. This reader's
observations are the input to that work, not a completed ingestion of those discs.

Format references consulted: ScummVM's
[archive/cast loader](https://github.com/scummvm/scummvm/blob/master/engines/director/cast.cpp),
[movie library mapping](https://github.com/scummvm/scummvm/blob/master/engines/director/movie.cpp),
[Lingo reader](https://github.com/scummvm/scummvm/blob/master/engines/director/lingo/lingo-bytecode.cpp),
and [score reader](https://github.com/scummvm/scummvm/blob/master/engines/director/score.cpp).
Implementation is a small independent observational parser; no ScummVM code or
runtime dependencies are bundled.
