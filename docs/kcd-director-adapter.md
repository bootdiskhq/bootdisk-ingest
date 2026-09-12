# Experimental pre-DTX K-CD adapter

`python -m bootdisk_ingest` now selects the Director adapter when root `K.DTX`
is absent. A present K.DTX always takes precedence, including a malformed DTX:
parsing errors do not silently switch formats. DTX manifests retain schema 0.9.
Director manifests use **`kcd-director-experimental-1`** and source format
`kcd-director-d6-v1`; consumers must explicitly opt into that projection.

The adapter requires root `K-CN.dxr` and `Constant.cxt`, matched using the core's
exact-first, unambiguous case-insensitive inventory lookup. Constant is bound
through its declared MCsL library ID and validated DRCF member bounds. Original
authoring-drive paths are evidence only; they are never opened. An available Norsk.cxt is also linked when the movie declares Norsk.cst or
Norsk.cxt. Other external casts remain explicitly unresolved.

This profile is qualified with K-CD **1/2000 and 4/2000**, Director 6 version
0x04c7. Other discs may be rejected or need further qualification. There are no
issue-specific executable tables or hard-coded expected entry counts in the
adapter. Binary parsing stays in `formats/director`; magazine menu conventions
stay in `adapters/kcd/director.py`. No new runtime dependency is required.

## Selection and evidence

This is static structural analysis, **not a Lingo interpreter or proof of runtime
reachability**. Its scope is the game and KDisk program menus, not every section
or every executable on a disc. Entry selection is an interpretation:

* Begin with the qualified game state `Spil2`. Follow literal game destinations
  in frame actions and score-linked mouseUp buttons. The game idle-label
  conventions identify groups; title text is read from channel 10, description
  from channel 14, resolving the actual library/member references.
* Begin with `KDisk1Mere`. Clickable text sprites supply program titles and detail
  destinations. Follow each menu action's `KxD6` next-page state and its
  score-linked button to the next menu. Stop on a visited page. A copied fourth
  menu in 4/2000 consequently does not become three extra catalog entries.
* Duplicate labels are retained. `K1D6` occurs more than once: next-page state
  selection requires the same frame action as the current menu, and reports all
  label frames. This is a structural profile rule, not emulation of Director's
  duplicate-label resolution. Ambiguous selected states are rejected.
* Detail states are restricted to the selected anchor and destinations named
  by its frame action, with the same library/member action reference. Merely
  sharing a script name, appearing elsewhere on the timeline, or containing an
  executable string does not select a program.
* The corresponding `K<n>Chicken` / `S<n>Chicken` label is an ordinal K-CD
  convention. Direct launch controls must themselves contain a literal mouseUp
  `go` to that warning label. The warning continue control uses the qualified
  channel 91 convention. Missing members and missing literal launch calls stay
  unresolved. Neither branch is copied over the other.
* Other launch controls on these pages, such as DirectX installation, remain in
  `evidence.other_launch_controls`. They are not treated as the program's own
  installer or included in its primary reference validation.

Each title, text and launch carries frame, channel, library/member and resource
references. Launch evidence includes handler, Lscr-relative instruction offset,
function and exact byte arguments. Source files have SHA-256 identities, and
`source.library_sources` maps library IDs to those observed files. Original byte
strings are retained as base64 alongside a CP1252 display view. Source Director
files themselves remain external preservation objects, not embedded archives.

Program descriptions use a deliberately narrow **heuristic**: the unique text
of at least 80 bytes in the corresponding overview frame. Otherwise description
is null. All overview texts and the selected description source remain in the
entry so this interpretation can be revised. Full detail-page text observations
are retained separately; these can include instructions or reusable UI text.

## Launch paths and validation

Qualified literal calls are `baRunProgram(path, mode, flags)` and
`baShell("open", filename, "", working_directory, mode)`. In the latter case,
the working directory participates in the disc-relative path. Absolute paths,
traversal, malformed strings, nonempty shell arguments and unknown signatures
are not guessed. The adapter never executes any of these calls.

Windows separators are interpreted as path separators. Source argument bytes
and spelling survive; resolved inventory spelling and case fallback are recorded
separately. Ambiguous fallback remains an unresolved target. Different resolved
physical paths are not collapsed merely because their casing is similar.

Both launch branches are retained. Different targets produce
`conflicting_launch_targets`, even if one file happens to exist. There is no
silent repair or preferred branch. `normalized.installer` and `normalized.run`
remain null: the adapter does not certify which action is an installer.

Entry content identity covers only **unique resolved primary launch files**.
It is not a software-package identity or a recursive directory grouping. Disc
identity and the complete file inventory remain independent preservation data.
Unselected launch scripts are listed in `source.unselected_launch_scripts`;
that classification does not establish whether they are stale or reachable
through some unanalysed section. Free-list scripts are not active evidence.

`--strict` writes the JSON, then returns 1 for missing primary launch files,
conflicting targets, unresolved primary branches/targets, or an empty result.
Input/profile errors return 2 without writing a partial result. Ordinary mode
returns 0 when observation succeeds, even if the manifest reports issues.
Validation concerns static primary launch-reference consistency, not complete
catalog reconstruction or runtime behavior.

## Linux ISO test

Mount the ISO with your usual read-only workflow, then run from the checkout:

```sh
python3 -m bootdisk_ingest /path/to/mounted-disc \
  --image /path/to/original.iso \
  --output /path/to/results/kcd-director.json --strict
```

Use your actual paths and an existing output directory outside the mounted disc.
`--image` is optional, independently hashes the image and inspects ISO9660; it
does not mount it or prove that the directory came from it. To replace a previous
result deliberately, add `--force`. The JSON contains the evidence needed to
investigate the reported issues.

Expected qualified results:

| Disc | Program/game candidates | Menu pages | Known structural issues |
| --- | ---: | ---: | --- |
| 1/2000 | 21 | 4 | Laid Back direct branch unresolved; four NHL-versus-warning conflicts; file checks depend on the supplied disc inventory |
| 4/2000 | 16 | 3 | Geometra images direct branch unresolved; Albert Åberg warning continue unresolved |

The full mounted 4/2000 disc yields 16 unique primary launch files, all found.
Strict mode still returns 1 for the two unresolved branches. This is expected
and should not be suppressed. The 1/2000 local qualification uses original
movie/cast bytes only; it is not a new full-disc inventory verification.

Run synthetic and existing tests with:

```sh
python3 -m unittest discover -s tests -v
```

Optional original-media regression tests (each directory contains its own
K-CN.dxr and Constant.cxt):

```sh
BOOTDISK_DIRECTOR_FIXTURES=/path/to/1-2000 \
BOOTDISK_DIRECTOR_KCD4_FIXTURES=/path/to/4-2000 \
python3 -m unittest discover -s tests -v
```

No original media are distributed with the repository or patch.

File copying is now available; see [first extraction](extraction.md).
